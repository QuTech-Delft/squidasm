from timeit import default_timer as timer
from typing import Dict

from qlink_interface import LinkLayerRecv

from netsquid_magic.link_layer import LinkLayerService
from netsquid_magic.sleeper import Sleeper

from netqasm.backend.network_stack import BaseNetworkStack, Address


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
        self._link_layer_services: Dict[int, LinkLayerService] = link_layer_services

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
        purpose_id = self.get_purpose_id(
            remote_node_id=remote_address.node_id,
            epr_socket_id=local_address.epr_socket_id,
        )
        return LinkLayerRecv(
            remote_node_id=remote_address.node_id,
            purpose_id=purpose_id,
        )

    # NOTE this is used for now since we communicate directly to the link layer
    def get_purpose_id(self, remote_node_id, epr_socket_id):
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
