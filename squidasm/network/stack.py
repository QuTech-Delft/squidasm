# from time import sleep
from collections import defaultdict
from timeit import default_timer as timer
from typing import List

import netsquid as ns
from qlink_interface import LinkLayerRecv

from netsquid_magic.link_layer import (
    LinkLayerService,
    MagicLinkLayerProtocol,
    SingleClickTranslationUnit,
)
from netsquid_magic.sleeper import Sleeper

from netqasm.network_stack import BaseNetworkStack, Address
from .setup import BackendNetwork

from netqasm.output import EntanglementStage
from squidasm.output import InstrLogger


# NOTE This is a hack for now to have something that the signaling protocol would do
class SignalingProtocol:
    def __init__(self):
        self._circuits = {}
        # NOTE for now let the protocol keep track of what purpose IDs to use in the
        # link layer requests since we don't use a network layer yet
        self._purpose_ids = {}
        self._next_purpose_id = 0

    def reset(self):
        self.__init__()

    def setup_circuit(self, local_address, remote_address):
        circuit_id = self.get_circuit_id(
            local_address=local_address,
            remote_address=remote_address,
        )
        self._circuits[(local_address, remote_address)] = circuit_id

    def get_circuit_id(self, local_address, remote_address):
        return hash(frozenset([
            (local_address.node_id, local_address.epr_socket_id),
            (remote_address.node_id, remote_address.epr_socket_id),
        ]))

    def has_circuit(self, local_address, remote_address):
        return (
            (local_address, remote_address) in self._circuits and
            (remote_address, local_address) in self._circuits
        )

    def _assign_purpose_id(self, local_address, remote_address):
        keys = [
            # Local node ID, remote Node ID, local epr socket ID
            (local_address.node_id, remote_address.node_id, local_address.epr_socket_id),
            (remote_address.node_id, local_address.node_id, remote_address.epr_socket_id),
        ]
        purpose_id = None
        for key in keys:
            if key in self._purpose_ids:
                purpose_id = self._purpose_ids[key]
        # If not assigned yet give it a new
        if purpose_id is None:
            purpose_id = self._next_purpose_id
            self._next_purpose_id += 1
        for key in keys:
            self._purpose_ids[key] = purpose_id

    def _get_purpose_id(self, node_id, remote_node_id, epr_socket_id):
        purpose_id = self._purpose_ids.get((node_id, remote_node_id, epr_socket_id))
        if purpose_id is None:
            raise ValueError(f"Not a known circuit for node with ID {node_id}, "
                             f"to remote node with ID {remote_node_id} and "
                             f"with EPR socket ID {epr_socket_id}")
        return purpose_id


# A single instance of the (hack) signaling protocol
_SIGNALING_PROTOCOL = SignalingProtocol()


def reset_network():
    _SIGNALING_PROTOCOL.reset()


class NetworkStack(BaseNetworkStack):
    def __init__(self, node, link_layer_services):
        self._node = node
        self._link_layer_services = link_layer_services

        self._signaling_protocol = _SIGNALING_PROTOCOL

        self._sleeper = Sleeper()

    def put(self, request):
        remote_node_id = request.remote_node_id
        # For now use only link layer
        link_layer_service = self._link_layer_services.get(remote_node_id)
        if link_layer_service is None:
            raise ValueError(f"The node with ID {remote_node_id} is not known to the network")
        return link_layer_service.put(request)

    def setup_epr_socket(self, epr_socket_id, remote_node_id, remote_epr_socket_id, timeout=5):
        """Asks the network stack to setup circuits to be used"""
        local_address = Address(
            node_id=self._node.ID,
            epr_socket_id=epr_socket_id,
        )
        remote_address = Address(
            node_id=remote_node_id,
            epr_socket_id=remote_epr_socket_id,
        )
        # NOTE this is needed since we directly talk to the link layer for now
        self._setup_recv_rule(
            local_address=local_address,
            remote_address=remote_address,
        )
        # Request to setup the circuit
        self._signaling_protocol.setup_circuit(
            local_address=local_address,
            remote_address=remote_address,
        )
        # Wait for the circuit to be established
        yield from self._wait_for_remote_node(
            local_address=local_address,
            remote_address=remote_address,
            timeout=timeout,
        )

    def _setup_recv_rule(self, local_address, remote_address):
        self._signaling_protocol._assign_purpose_id(
            local_address=local_address,
            remote_address=remote_address,
        )
        recv_request = self._get_recv_request(
            local_address=local_address,
            remote_address=remote_address,
        )
        self.put(request=recv_request)

    def _get_recv_request(self, local_address, remote_address):
        # NOTE using purpose ID for now since we communicate with link layer
        purpose_id = self._get_purpose_id(
            remote_node_id=remote_address.node_id,
            epr_socket_id=local_address.epr_socket_id,
        )
        return LinkLayerRecv(
            remote_node_id=remote_address.node_id,
            purpose_id=purpose_id,
        )

    # NOTE this is used for now since we communicate directly to the link layer
    def _get_purpose_id(self, remote_node_id, epr_socket_id):
        return self._signaling_protocol._get_purpose_id(
            node_id=self._node.ID,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
        )

    def _wait_for_remote_node(self, local_address, remote_address, timeout=1):
        t_start = timer()
        while True:
            if self._signaling_protocol.has_circuit(local_address=local_address, remote_address=remote_address):
                break
            # Wait a little until checking again
            yield self._sleeper.sleep()
            now = timer()
            if (now - t_start) > timeout:
                raise TimeoutError("Remote node did not initialize the correct rules")


class MagicNetworkLayerProtocol(MagicLinkLayerProtocol):
    """
    Same as a MagicLinkLayerProtocol, but contains information about a path in the network.
    This path is not actually used by the magic protocol.
    Furthermore, it logs requests and deliveries to the NetworkLogger of the network.
    """
    def __init__(self, nodes, magic_distributor, translation_unit, path: List[str], network):
        super().__init__(
            nodes=nodes, magic_distributor=magic_distributor, translation_unit=translation_unit)

        self.path = path
        self.network = network

    def _handle_create_request(self, node_id, request):
        node0 = self.nodes[0].name
        node1 = self.nodes[1].name
        qubit_groups = InstrLogger._get_qubit_groups()

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_stage=EntanglementStage.START,
            nodes=[node0, node1],
            qids=[None, None],
            qubit_groups=qubit_groups,
            path=[node for node in self.path],
            msg=f"start entanglement creation between {node0} and {node1}",
        )

        return super()._handle_create_request(node_id=node_id, request=request)

    def _handle_delivery(self, event):
        delivery = self._magic_distributor.peek_delivery(event)
        memory_positions = delivery.memory_positions

        super()._handle_delivery(event)

        node0 = self.nodes[0].name
        node1 = self.nodes[1].name
        node0_pos, node1_pos = memory_positions.values()
        qubit0 = node0_pos[0]
        qubit1 = node1_pos[0]
        qubit_groups = InstrLogger._get_qubit_groups()

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_stage=EntanglementStage.FINISH,
            nodes=[node0, node1],
            qids=[qubit0, qubit1],
            qubit_groups=qubit_groups,
            path=[node for node in self.path],
            msg=f"entanglement created between {node0} and {node1}",
        )


def create_link_layer_services(network: BackendNetwork, reaction_handlers):
    """
    Create a dictionary mapping (node name, remote node ID) to a LinkLayerService object.
    A service is created for each 'link' that is in the `network` object.

    Returns the dictionary of service objects.
    """
    link_layer_services = defaultdict(dict)

    for link in network.links:  # type(link) = MagicDistributor
        node_pair = link.nodes[0]
        path = network.paths[(node_pair[0].name, node_pair[1].name)]

        magic_protocol = MagicNetworkLayerProtocol(
            nodes=node_pair,
            magic_distributor=link,
            translation_unit=SingleClickTranslationUnit(),
            path=path,
            network=network,
        )

        for node, remote_node in [node_pair, reversed(node_pair)]:
            reaction_handler = reaction_handlers[node.name]
            link_layer_service = LinkLayerService(
                node=node,
                magic=True,
                magic_protocol=magic_protocol,
                reaction_handler=reaction_handler,
            )
            link_layer_services[node.name][remote_node.ID] = link_layer_service

    return link_layer_services


def create_network_stacks(network: BackendNetwork, reaction_handlers):
    """
    Create a NetworkStack object for each node in the `network`.

    Parameters
    ----------
    `reaction_handlers`: dict
        Keys are the names of the nodes.
        Values are the reaction handler used in the node's link layer service.

    Returns
    -------
    A dictionary mapping node names to newly created NetworkStack objects.
    """
    link_layer_services = create_link_layer_services(network, reaction_handlers)
    network_stacks = {}
    for node_name, node in network.nodes.items():
        network_stack = NetworkStack(node=node, link_layer_services=link_layer_services[node_name])
        network_stacks[node_name] = network_stack

    return network_stacks
