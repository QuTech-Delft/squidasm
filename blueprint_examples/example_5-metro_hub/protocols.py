from typing import Generator
import netsquid as ns
from netsquid.protocols import Protocol, Signals
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from blueprint.network import ProtocolContext
from pydynaa import EventExpression


class AliceProtocol(Protocol):
    def __init__(self, context: ProtocolContext, peer: str):
        self.peer = peer
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.peer]
        egp = self.context.egp[self.peer]
        qdevice = self.context.node.qdevice

        for _ in range(10):
            yield self.await_port_input(port)
            message = port.rx_input()
            print(f"{ns.sim_time()} ns: {self.context.node.name} receives: {message.items[0]}")

            request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.peer], number=1)
            egp.put(request)

            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            result = qdevice.measure(received_qubit_mem_pos)[0]
            qdevice.discard(received_qubit_mem_pos)

            print(f"{ns.sim_time()} ns: {self.context.node.name} Created EPR with {self.peer} and measures {result}")

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()


class BobProtocol(Protocol):
    def __init__(self, context: ProtocolContext, peer: str):
        self.context = context
        self.add_signal(Signals.FINISHED)
        self.peer = peer

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.peer]
        port = self.context.ports[self.peer]
        qdevice = self.context.node.qdevice

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.peer]))

        for _ in range(10):
            port.tx_output("Ready to start entanglement")

            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id

            result = qdevice.measure(positions=[received_qubit_mem_pos])[0]
            qdevice.discard(received_qubit_mem_pos)
            print(f"{ns.sim_time()} ns: {self.context.node.name} Created EPR with {self.peer} and measures {result}")

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
