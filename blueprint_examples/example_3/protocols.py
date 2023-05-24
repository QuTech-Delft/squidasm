from typing import Generator

from netsquid.components import INSTR_X
from netsquid.components import QuantumProcessor
from netsquid.protocols import Protocol, Signals
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from blueprint.network import ProtocolContext
from pydynaa import EventExpression


class AliceProtocol(Protocol):
    PEER = "Bob"

    def __init__(self, context: ProtocolContext):
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.PEER]

        # create request
        request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.PEER], number=1)
        egp.put(request)

        # Await request completion
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos])
        yield self.await_program(qdevice)


    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()


class BobProtocol(Protocol):
    PEER = "Alice"

    def __init__(self, context: ProtocolContext):
        self.context = context
        egp = self.context.egp[self.PEER]

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.PEER]

        # Wait for a signal from the EGP.
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos])
        yield self.await_program(qdevice)

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
