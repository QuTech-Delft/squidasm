from __future__ import annotations

import itertools
from typing import Any, Dict, List

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

from squidasm.run.stack.build import build_generic_qdevice, build_nv_qdevice
from squidasm.run.stack.config import (
    DepolariseLinkConfig,
    GenericQDeviceConfig,
    HeraldedLinkConfig,
    NVLinkConfig,
    NVQDeviceConfig,
    StackNetworkConfig,
)
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program
from squidasm.sim.stack.stack import NodeStack, StackNetwork


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


def _setup_network(config: StackNetworkConfig) -> StackNetwork:
    assert len(config.stacks) <= 2
    assert len(config.links) <= 1

    stacks: Dict[str, NodeStack] = {}
    link_prots: List[MagicLinkLayerProtocol] = []

    for cfg in config.stacks:
        if cfg.qdevice_typ == "nv":
            qdevice_cfg = cfg.qdevice_cfg
            if not isinstance(qdevice_cfg, NVQDeviceConfig):
                qdevice_cfg = NVQDeviceConfig(**cfg.qdevice_cfg)
            qdevice = build_nv_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            stack = NodeStack(cfg.name, qdevice_type="nv", qdevice=qdevice)
        elif cfg.qdevice_typ == "generic":
            qdevice_cfg = cfg.qdevice_cfg
            if not isinstance(qdevice_cfg, GenericQDeviceConfig):
                qdevice_cfg = GenericQDeviceConfig(**cfg.qdevice_cfg)
            qdevice = build_generic_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            stack = NodeStack(cfg.name, qdevice_type="generic", qdevice=qdevice)
        NetSquidContext.add_node(stack.node.ID, cfg.name)
        stacks[cfg.name] = stack

    for (_, s1), (_, s2) in itertools.combinations(stacks.items(), 2):
        s1.connect_to(s2)

    for link in config.links:
        stack1 = stacks[link.stack1]
        stack2 = stacks[link.stack2]
        if link.typ == "perfect":
            link_dist = PerfectStateMagicDistributor(
                nodes=[stack1.node, stack2.node], state_delay=1000.0
            )
        elif link.typ == "depolarise":
            link_cfg = link.cfg
            if not isinstance(link_cfg, DepolariseLinkConfig):
                link_cfg = DepolariseLinkConfig(**link.cfg)
            prob_max_mixed = fidelity_to_prob_max_mixed(link_cfg.fidelity)
            link_dist = DepolariseWithFailureMagicDistributor(
                nodes=[stack1.node, stack2.node],
                prob_max_mixed=prob_max_mixed,
                prob_success=link_cfg.prob_success,
                t_cycle=link_cfg.t_cycle,
            )
        elif link.typ == "nv":
            link_cfg = link.cfg
            if not isinstance(link_cfg, NVLinkConfig):
                link_cfg = NVLinkConfig(**link.cfg)
            link_dist = NVSingleClickMagicDistributor(
                nodes=[stack1.node, stack2.node],
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
                [stack1.node, stack2.node], connection
            )
        else:
            raise ValueError

        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[stack1.node, stack2.node],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        stack1.assign_ll_protocol(link_prot)
        stack2.assign_ll_protocol(link_prot)

        link_prots.append(link_prot)

    return StackNetwork(stacks, link_prots)


def _run(network: StackNetwork) -> List[Dict[str, Any]]:
    assert len(network.stacks) <= 2
    assert len(network.links) <= 1

    for link in network.links:
        link.start()

    for _, stack in network.stacks.items():
        stack.start()

    ns.sim_run()

    return [stack.host.get_results() for _, stack in network.stacks.items()]


def run(
    config: StackNetworkConfig, programs: Dict[str, Program], num_times: int = 1
) -> List[Dict[str, Any]]:
    network = _setup_network(config)

    NetSquidContext.set_nodes({})
    for name, stack in network.stacks.items():
        NetSquidContext.add_node(stack.node.ID, name)

    GlobalSimData.set_network(network)
    for name, program in programs.items():
        network.stacks[name].host.enqueue_program(program, num_times)

    results = _run(network)
    return results
