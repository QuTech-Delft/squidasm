from dataclasses import dataclass
from typing import Dict

from netsquid.components import Port
from netsquid.protocols import ServiceProtocol
from netsquid_driver.classical_routing_service import (
    ClassicalRoutingService,
    RemoteServiceRequest,
)

from pydynaa import EventExpression
from squidasm.sim.stack.common import PortListener
from squidasm.sim.stack.qnos import QnosComponent


@dataclass
class ReqQNOSMessage:
    """Request to send a message to a QNOS component on a remote node"""

    origin: str
    message: str


class QNOSNetworkService(ServiceProtocol):
    """Interface with the Netsquid network for routing communication between remote QNOS components."""

    RECEIVED_MESSAGE = "Received message"

    def __init__(self, node, qnos_component: QnosComponent):
        ServiceProtocol.__init__(self, node=node, name=node.name)
        self.qnos_comp = qnos_component
        self.node_id_name_mapping: Dict[str, int] = {}
        self.register_request(ReqQNOSMessage, self.receive_qnos_message)
        self._listener_to_name: Dict[PortListener, str] = {}
        self._port_to_name: Dict[Port, str] = {}

    def receive_qnos_message(self, req: ReqQNOSMessage):
        """Receive a message from a remote QNOS component.

        Will forward received communication to local QNOS component.
        """
        if req.origin not in self.node_id_name_mapping.keys():
            raise RuntimeError(
                f"Node: {self.node.name} received QNOS request"
                f" from unregistered peer {req.origin}"
            )

        remote_id = self.node_id_name_mapping[req.origin]
        port = self.qnos_comp.peer_in_port(remote_id)
        port.tx_input(req.message)

    def send_qnos_message(self, msg: str, target: str):
        """Send a message to a remote QNOS component"""
        service_request = RemoteServiceRequest(
            request=ReqQNOSMessage(origin=self.node.name, message=msg),
            origin=self.node.name,
            service=QNOSNetworkService,
            targets=[target],
        )

        self.node.driver.services[ClassicalRoutingService].put(service_request)

    def register_remote_node(self, node_name: str, node_id: int):
        assert self.qnos_comp.peer_in_port(node_id) is not None
        assert self.qnos_comp.peer_out_port(node_id) is not None
        self.node_id_name_mapping[node_name] = node_id

        self._port_to_name[self.qnos_comp.peer_out_port(node_id)] = node_name

    def run(self):
        # Without any ports there is nothing to wait and respond for
        if len(self._port_to_name) == 0:
            return

        any_port_output_expr = self._build_combined_port_output_event_expr()
        while True:
            yield any_port_output_expr
            for event in any_port_output_expr.triggered_events:
                port = event.source
                assert isinstance(port, Port)
                remote_node = self._port_to_name[port]
                for item in port.rx_output().items:
                    self.send_qnos_message(item, target=remote_node)

    def _build_combined_port_output_event_expr(self) -> EventExpression:
        ports = list(self._port_to_name.keys())

        evt_expr = self.await_port_output(ports[0])
        for port in ports[1:]:
            evt_expr = evt_expr | self.await_port_output(port)

        return evt_expr

    def start(self) -> None:
        super().start()
        for listener in self._listener_to_name.keys():
            listener.start()

    def stop(self) -> None:
        for listener in self._listener_to_name.keys():
            listener.stop()
        super().stop()
