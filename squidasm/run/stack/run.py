from __future__ import annotations

from typing import Any, Dict, List

import netsquid as ns
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
)

from blueprint.base_configs import StackNetworkConfig
from blueprint.setup_network import ProtocolController, NetworkBuilder
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program
from squidasm.sim.stack.stack import NodeStack, StackNetwork, ProcessingNode


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


def _setup_network(config: StackNetworkConfig) -> StackNetwork:
    assert len(config.stacks) <= 2
    assert len(config.links) <= 1

    network = NetworkBuilder.build(config)

    stacks: Dict[str, NodeStack] = {}

    for node_id, node in network.nodes.items():
        assert isinstance(node, ProcessingNode)
        stack = NodeStack(name=node_id, node=node, qdevice_type=node.qmemory_typ)
        NetSquidContext.add_node(stack.node.ID, node_id)
        stacks[node_id] = stack

    for id_tuple, egp in network.egp.items():
        node_id, peer_id = id_tuple
        stacks[node_id].assign_egp(egp)

    link_prots: List[MagicLinkLayerProtocol] = []

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
