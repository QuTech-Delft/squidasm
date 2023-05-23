from typing import Generator

import netsquid as ns
from blueprint.setup_network import ProtocolContext
from netsquid.components import QuantumProcessor
from netsquid.components.component import Qubit
from netsquid.protocols import Protocol, Signals
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from pydynaa import EventExpression
from squidasm.sim.stack.egp import EgpProtocol
from squidasm.sim.stack.stack import ProcessingNode


class AliceProtocol(Protocol):
    PEER = "Bob"

    def __init__(self, context: ProtocolContext):
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.PEER]
        request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.PEER], number=1)

        egp.put(request)
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        qdevice: QuantumProcessor = self.context.node.qdevice
        qubit: Qubit = qdevice.peek(positions=[0])[0]

        print(ns.qubits.qubitapi.reduced_dm(qubit.qstate.qubits))

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

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
