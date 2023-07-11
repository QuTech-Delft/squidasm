from __future__ import annotations

from typing import Any, Dict, List

import netsquid as ns
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
)
from squidasm.sim.stack.csocket import ClassicalSocket

from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.run import get_default_builder
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program
from squidasm.sim.stack.stack import NodeStack, StackNetwork, ProcessingNode
import itertools


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


def _setup_network(config: StackNetworkConfig) -> StackNetwork:
    builder = get_default_builder()
    network = builder.build(config)

    stacks: Dict[str, NodeStack] = {}

    for node_name, node in network.nodes.items():
        assert isinstance(node, ProcessingNode)
        stack = NodeStack(name=node_name, node=node, qdevice_type=node.qmemory_typ)
        NetSquidContext.add_node(stack.node.ID, node_name)
        stacks[node_name] = stack

    for id_tuple, egp in network.egp.items():
        node_name, peer_name = id_tuple
        stacks[node_name].assign_egp(network.node_name_id_mapping[peer_name], egp)

    for s1, s2 in itertools.combinations(stacks.values(), 2):
        s1.qnos.netstack.register_peer(s2.node.ID)
        s1.qnos_comp.register_peer(s2.node.ID)
        s2.qnos.netstack.register_peer(s1.node.ID)
        s2.qnos_comp.register_peer(s1.node.ID)

    csockets: Dict[(str, str): ClassicalSocket] = {}
    for node_pair in network.ports.keys():
        node_name = node_pair[0]
        peer_name = node_pair[1]
        port = network.ports[(node_name, peer_name)]

        # TODO app name is unknown here
        csocket = ClassicalSocket(port, app_name=node_name, remote_app_name=peer_name)
        csockets[(node_name, peer_name)] = csocket
        stacks[node_name].host.register_csocket(peer_name, csocket)

    link_prots: List[MagicLinkLayerProtocol] = []
    # TODO cheaty start protocols here
    builder.protocol_controller.start_all()

    return StackNetwork(stacks, link_prots, csockets)


def _run(network: StackNetwork) -> List[List[Dict[str, Any]]]:
    """Run the protocols of a network and programs running in that network.

    NOTE: For now, only two nodes and a single link are supported.

    :param network: `StackNetwork` representing the nodes and links
    :return: final results of the programs
    """
    #assert len(network.stacks) <= 2
    #assert len(network.links) <= 1

    # start all link layer protocols
    # TODO used to be start protocols here
    #ProtocolController.start_all()

    # Start the node protocols.
    for _, stack in network.stacks.items():
        stack.start()

    for csocket in network.csockets.values():
        csocket.start()

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
