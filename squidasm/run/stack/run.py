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

from blueprint.setup_network import NodeBuilder, ClassicalConnectionBuilder, LinkBuilder, EGPBuilder, ProtocolController
from blueprint.links import (
    DepolariseLinkConfig,
    HeraldedLinkConfig,
    NVLinkConfig,
)
from blueprint.qdevices import (
    GenericQDeviceConfig,
    NVQDeviceConfig,
    build_nv_qdevice,
    build_generic_qdevice,
)
from blueprint.base_configs import LinkConfig, StackConfig, StackNetworkConfig
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program
from squidasm.sim.stack.stack import NodeStack, StackNetwork, ProcessingNode


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


def _setup_network(config: StackNetworkConfig) -> StackNetwork:
    assert len(config.stacks) <= 2
    assert len(config.links) <= 1

    stacks: Dict[str, NodeStack] = {}
    link_prots: List[MagicLinkLayerProtocol] = []

    qdevice_nodes = NodeBuilder.build(config)

    for node in qdevice_nodes:
        assert isinstance(node, ProcessingNode)
        stack = NodeStack(name=node.name, node=node, qdevice_type=node.qmemory_typ)
        NetSquidContext.add_node(stack.node.ID, node.name)
        stacks[node.name] = stack

    ClassicalConnectionBuilder.build(config, qdevice_nodes)

    link_dict = LinkBuilder.build(config, qdevice_nodes)

    for node in qdevice_nodes:
        egp_dict = EGPBuilder.build(node, link_dict)
        assert len(egp_dict) == 1
        for peer_name, egp in egp_dict.items():
            stacks[node.name].assign_egp(egp)

    return StackNetwork(stacks, link_prots)


def _run(network: StackNetwork) -> List[List[Dict[str, Any]]]:
    """Run the protocols of a network and programs running in that network.

    NOTE: For now, only two nodes and a single link are supported.

    :param network: `StackNetwork` representing the nodes and links
    :return: final results of the programs
    """
    assert len(network.stacks) <= 2
    assert len(network.links) <= 1

    # start all link layer protocols
    ProtocolController.start_all()

    # Start the node protocols.
    for _, stack in network.stacks.items():
        stack.start()

    # Start the NetSquid simulation.
    ns.sim_run()

    return [stack.host.get_results() for _, stack in network.stacks.items()]


def run(
    config: StackNetworkConfig, programs: Dict[str, Program], num_times: int = 1
) -> List[List[Dict[str, Any]]]:
    """Run programs on a network specified by a network configuration.

    :param config: configuration of the network
    :param programs: dictionary of node names to programs
    :param num_times: numbers of times to run the programs, defaults to 1
    :return: program results, outer list is per stack, inner list is per program iteration
    """
    network = _setup_network(config)

    NetSquidContext.set_nodes({})
    for name, stack in network.stacks.items():
        NetSquidContext.add_node(stack.node.ID, name)

    GlobalSimData.set_network(network)
    for name, program in programs.items():
        network.stacks[name].host.enqueue_program(program, num_times)

    results = _run(network)
    return results
