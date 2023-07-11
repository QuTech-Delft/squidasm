from typing import Generator

import netsquid as ns
from netsquid.components import INSTR_X
from netsquid.components import QuantumProcessor
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from netsquid_netbuilder.protocol_base import BlueprintProtocol
from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    PEER = "Bob"

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.PEER]
        egp = self.context.egp[self.PEER]

        yield self.await_port_input(port)
        message = port.rx_input()
        print(f"{ns.sim_time()} ns: Alice receives: {message.items[0]}")

        # create request
        request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.PEER], number=1)
        egp.put(request)

        # Await request completion
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id
        print(f"{ns.sim_time()} ns: Alice completes entanglement generation")

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos])
        yield self.await_program(qdevice)
        print(f"{ns.sim_time()} ns: Alice completes applying X gate")


class BobProtocol(BlueprintProtocol):
    PEER = "Alice"

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.PEER]
        egp = self.context.egp[self.PEER]

        msg = "Hello"
        port.tx_output(msg)
        print(f"{ns.sim_time()} ns: Bob sends: {msg}")

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))

        # Wait for a signal from the EGP.
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id
        print(f"{ns.sim_time()} ns: Bob completes entanglement generation")

        # Apply Pauli X gate
        qdevice: QuantumProcessor = self.context.node.qdevice
        qdevice.execute_instruction(instruction=INSTR_X, qubit_mapping=[received_qubit_mem_pos])
        yield self.await_program(qdevice)
        print(f"{ns.sim_time()} ns: Bob completes applying X gate")


