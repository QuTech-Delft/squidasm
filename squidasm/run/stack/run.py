from __future__ import annotations

import itertools
from typing import Any, Dict, List, Union

import netsquid as ns
from netsquid_driver.classical_socket_service import (
    ClassicalSocket,
    ClassicalSocketService,
)
from netsquid_driver.connectionless_socket_service import ConnectionlessSocketService
from netsquid_magic.link_layer import MagicLinkLayerProtocol
from netsquid_netbuilder.network_config import NetworkConfig

from squidasm.run.stack.build import create_stack_network_builder
from squidasm.run.stack.config import StackNetworkConfig, _convert_stack_network_config
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program
from squidasm.sim.stack.qnos_network_service import QNOSNetworkService
from squidasm.sim.stack.stack import NodeStack, StackNetwork, StackNode


def _setup_network(config: NetworkConfig) -> StackNetwork:
    NetSquidContext.reset()
    builder = create_stack_network_builder()
    network = builder.build(config)

    stacks: Dict[str, NodeStack] = {}

    for node_name, node in network.end_nodes.items():
        assert isinstance(node, StackNode)
        stack = NodeStack(name=node_name, node=node, qdevice_type=node.qmemory_typ)
        NetSquidContext.add_node(stack.node.ID, node_name)
        stacks[node_name] = stack

    for id_tuple, egp in network.egp.items():
        node_name, peer_name = id_tuple
        stacks[node_name].assign_egp(network.node_name_id_mapping[peer_name], egp)

    for s1, s2 in itertools.combinations(stacks.values(), 2):
        s1.qnos_comp.register_peer(s2.node.ID)
        s1.qnos.netstack.register_peer(s2.node.ID)
        s2.qnos_comp.register_peer(s1.node.ID)
        s2.qnos.netstack.register_peer(s1.node.ID)

    for node_name, node in network.end_nodes.items():
        assert isinstance(node, StackNode)
        service = QNOSNetworkService(node, node.qnos_comp)
        node.driver.add_service(QNOSNetworkService, service)
        for remote_name, remote_node in network.end_nodes.items():
            if remote_name != node_name:
                service.register_remote_node(remote_name, remote_node.ID)

    # used to build ClassicalSockets here, now just import from network

    csockets: Dict[(str, str), ClassicalSocket] = {}

    for s1 in stacks.values():
        socket_service = ConnectionlessSocketService(node=s1.node)
        s1.node.driver.add_service(ClassicalSocketService, socket_service)
        for s2 in stacks.values():
            if s2 is s1:
                continue
            socket = socket_service.create_socket()
            socket.bind(port_name="0", remote_node_name=s2.node.name)
            socket.connect(remote_port_name="0", remote_node_name=s2.node.name)
            csockets[(s1.node.name, s2.node.name)] = socket
            network._protocol_controller.register(socket)

    for (node_name, peer_name), netsquid_socket in csockets.items():
        stacks[node_name].host.register_netsquid_socket(peer_name, netsquid_socket)

    link_prots: List[MagicLinkLayerProtocol] = []
    # TODO move this start to same method where stacks and ns.sim_run() are
    network.start()

    return StackNetwork(stacks, link_prots, csockets)


def _run(network: StackNetwork) -> List[List[Dict[str, Any]]]:
    """Run the protocols of a network and programs running in that network.

    :param network: `StackNetwork` representing the nodes and links
    :return: final results of the programs
    """

    # Start the node protocols.
    for _, stack in network.stacks.items():
        stack.start()

    # Start the NetSquid simulation.
    ns.sim_run()

    return [stack.host.get_results() for _, stack in network.stacks.items()]


def run(
    config: Union[NetworkConfig, StackNetworkConfig],
    programs: Dict[str, Program],
    num_times: int = 1,
) -> List[List[Dict[str, Any]]]:
    """Run programs on a network specified by a network configuration.

    :param config: configuration of the network
    :param programs: dictionary of node names to programs
    :param num_times: numbers of times to run the programs, defaults to 1
    :return: program results, outer list is per stack, inner list is per program iteration
    """
    if isinstance(config, StackNetworkConfig):
        config = _convert_stack_network_config(config)

    network = _setup_network(config)

    NetSquidContext.set_nodes({})
    for name, stack in network.stacks.items():
        NetSquidContext.add_node(stack.node.ID, name)

    GlobalSimData.set_network(network)
    for name, program in programs.items():
        network.stacks[name].host.enqueue_program(program, num_times)

    results = _run(network)
    return results
