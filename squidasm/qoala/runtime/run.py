from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional

import netsquid as ns
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    DepolariseWithFailureMagicDistributor,
    DoubleClickMagicDistributor,
    PerfectStateMagicDistributor,
)
from netsquid_nv.magic_distributor import NVSingleClickMagicDistributor
from netsquid_physlayer.heralded_connection import MiddleHeraldedConnection

from squidasm.qoala.runtime.config import (
    DepolariseLinkConfig,
    GenericQDeviceConfig,
    HeraldedLinkConfig,
    NVLinkConfig,
    NVQDeviceConfig,
    ProcNodeNetworkConfig,
)
from squidasm.qoala.runtime.context import SimulationContext
from squidasm.qoala.runtime.environment import GlobalEnvironment, GlobalNodeInfo
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.build import build_generic_qdevice, build_nv_qdevice
from squidasm.qoala.sim.globals import GlobalSimData
from squidasm.qoala.sim.procnode import ProcNode, ProcNodeNetwork


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


def _setup_network(
    config: ProcNodeNetworkConfig, rte: GlobalEnvironment
) -> ProcNodeNetwork:
    proc_nodes: Dict[str, ProcNode] = {}
    link_prots: List[MagicLinkLayerProtocol] = []

    # First add all nodes to the global environment ...
    for cfg in config.nodes:
        # TODO !!!
        # get HW info from config
        node_info = GlobalNodeInfo(cfg.name, 2, 1, 0, 0, 0, 0)
        rte.add_node(cfg.node_id, node_info)

    # ... so that the nodes know about all other nodes while building their components
    for cfg in config.nodes:
        if cfg.qdevice_typ == "nv":
            qdevice_cfg = cfg.qdevice_cfg
            if not isinstance(qdevice_cfg, NVQDeviceConfig):
                qdevice_cfg = NVQDeviceConfig(**cfg.qdevice_cfg)
            qdevice = build_nv_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            procnode = ProcNode(
                cfg.name,
                global_env=rte,
                qdevice_type="nv",
                qdevice=qdevice,
                node_id=cfg.node_id,
            )
        elif cfg.qdevice_typ == "generic":
            qdevice_cfg = cfg.qdevice_cfg
            if not isinstance(qdevice_cfg, GenericQDeviceConfig):
                qdevice_cfg = GenericQDeviceConfig(**cfg.qdevice_cfg)
            qdevice = build_generic_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            procnode = ProcNode(
                cfg.name,
                global_env=rte,
                qdevice_type="generic",
                qdevice=qdevice,
                node_id=cfg.node_id,
            )

        proc_nodes[cfg.name] = procnode

    for (_, s1), (_, s2) in itertools.combinations(proc_nodes.items(), 2):
        s1.connect_to(s2)

    for link in config.links:
        proc_node1 = proc_nodes[link.node1]
        proc_node2 = proc_nodes[link.node2]
        if link.typ == "perfect":
            link_dist = PerfectStateMagicDistributor(
                nodes=[proc_node1.node, proc_node2.node], state_delay=1000.0
            )
        elif link.typ == "depolarise":
            link_cfg = link.cfg
            if not isinstance(link_cfg, DepolariseLinkConfig):
                link_cfg = DepolariseLinkConfig(**link.cfg)
            prob_max_mixed = fidelity_to_prob_max_mixed(link_cfg.fidelity)
            link_dist = DepolariseWithFailureMagicDistributor(
                nodes=[proc_node1.node, proc_node2.node],
                prob_max_mixed=prob_max_mixed,
                prob_success=link_cfg.prob_success,
                t_cycle=link_cfg.t_cycle,
            )
        elif link.typ == "nv":
            link_cfg = link.cfg
            if not isinstance(link_cfg, NVLinkConfig):
                link_cfg = NVLinkConfig(**link.cfg)
            link_dist = NVSingleClickMagicDistributor(
                nodes=[proc_node1.node, proc_node2.node],
                length_A=link_cfg.length_A,
                length_B=link_cfg.length_B,
                full_cycle=link_cfg.full_cycle,
                cycle_time=link_cfg.cycle_time,
                alpha=link_cfg.alpha,
            )
        elif link.typ == "heralded":
            link_cfg = link.cfg
            if not isinstance(link_cfg, HeraldedLinkConfig):
                link_cfg = HeraldedLinkConfig(**link.cfg)
            connection = MiddleHeraldedConnection(
                name="heralded_conn", **link_cfg.dict()
            )
            link_dist = DoubleClickMagicDistributor(
                [proc_node1.node, proc_node2.node], connection
            )
        else:
            raise ValueError

        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[proc_node1.node, proc_node2.node],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        proc_node1.assign_ll_protocol(proc_node2.node.ID, link_prot)
        proc_node2.assign_ll_protocol(proc_node1.node.ID, link_prot)

        link_prots.append(link_prot)

    return ProcNodeNetwork(proc_nodes, link_prots)


def _run(network: ProcNodeNetwork) -> List[Dict[str, Any]]:
    """Run the protocols of a network and programs running in that network.

    :param network: `ProcNodeNetwork` representing the nodes and links
    :return: final results of the programs
    """

    # Start the link protocols.
    for link in network.links:
        link.start()

    # Start the node protocols.
    for _, node in network.nodes.items():
        node.start()

    # Start the NetSquid simulation.
    ns.sim_run()

    return [node.scheduler.get_results() for _, node in network.nodes.items()]


def run(
    config: ProcNodeNetworkConfig,
    programs: Dict[str, List[ProgramInstance]],
    schedules: Optional[Dict[str, Schedule]] = None,
    num_times: int = 1,
) -> List[Dict[str, Any]]:
    """Run programs on a network specified by a network configuration.

    :param config: configuration of the network
    :param programs: dictionary of node names to programs
    :param num_times: numbers of times to run the programs, defaults to 1
    :return: program results
    """
    # Create global runtime environment.
    rte = GlobalEnvironment()

    # Build the network. Info about created nodes will be added to the runtime environment.
    network = _setup_network(config, rte)

    ###########################################
    # TODO: pass context to simulation objects!
    ###########################################
    sim_data = GlobalSimData()
    sim_data.set_network(network)
    context = SimulationContext(global_env=rte, global_sim_data=sim_data)

    for name, program_list in programs.items():
        for program in program_list:
            network.nodes[name]._local_env.register_program(program)

    if schedules is not None:
        for name, schedule in schedules.items():
            network.nodes[name]._local_env.install_local_schedule(schedule)

    for name in programs.keys():
        network.nodes[name].install_environment()

    results = _run(network)
    return results
