from typing import Generator

import netsquid as ns
import netsquid.qubits.qubitapi
from netsquid.components import QuantumProcessor
from netsquid.components.component import Qubit
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        socket = self.context.sockets[self.PEER]
        egp = self.context.egp[self.PEER]

        message = yield from socket.recv()
        print(f"{ns.sim_time()} ns: Alice receives: {message}")

        number = 3
        # create request
        request = ReqCreateAndKeep(
            remote_node_id=self.context.node_id_mapping[self.PEER], number=number
        )
        egp.put(request)

        # Await request completion
        for _ in range(number):
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            print(f"{ns.sim_time()} ns: Alice completes entanglement generation and now has a qubit at mem_pos: {received_qubit_mem_pos}")

            qdevice: QuantumProcessor = self.context.node.qdevice
            qubit: Qubit = qdevice.peek(positions=received_qubit_mem_pos)[0]
            dm = netsquid.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
            print(f"{response.bell_state}")
            print(f"{dm}")

        yield self.await_timer(1000)

        number = 4
        request = ReqCreateAndKeep(
            remote_node_id=self.context.node_id_mapping[self.PEER], number=number
        )
        egp.put(request)
        for _ in range(number):
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            print(f"{ns.sim_time()} ns: Alice completes entanglement generation and now has a qubit at mem_pos: {received_qubit_mem_pos}")


class BobProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        socket = self.context.sockets[self.PEER]
        egp = self.context.egp[self.PEER]

        msg = "Hello"
        socket.send(msg)
        print(f"{ns.sim_time()} ns: Bob sends: {msg}")

        # TODO this commented out as no EGP level agreement system is yet in place in SwapASAP EGP and defaults to always accept
        #egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))

        while True:
            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            print(f"{ns.sim_time()} ns: Bob completes entanglement generation and now has a qubit at mem_pos: {received_qubit_mem_pos}")


