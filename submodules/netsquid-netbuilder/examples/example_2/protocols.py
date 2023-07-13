from typing import Generator

from netsquid.components import INSTR_X, QuantumProcessor
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    PEER = "Bob"

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.PEER]
        port = self.context.ports[self.PEER]

        yield self.await_port_input(port)

        # create request
        request = ReqCreateAndKeep(
            remote_node_id=self.context.node_id_mapping[self.PEER], number=1
        )
        egp.put(request)

        # Await request completion
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(
            instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos]
        )
        yield self.await_program(qdevice)


class BobProtocol(BlueprintProtocol):
    PEER = "Alice"

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.PEER]
        port = self.context.ports[self.PEER]

        port.tx_output("")
        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))

        # Wait for a signal from the EGP.
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(
            instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos]
        )
        yield self.await_program(qdevice)
