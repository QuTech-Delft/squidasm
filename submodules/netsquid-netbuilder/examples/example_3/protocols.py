from typing import Generator, List

import netsquid as ns
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from netsquid_netbuilder.protocol_base import BlueprintProtocol
from pydynaa import EventExpression


class ServerProtocol(BlueprintProtocol):
    def __init__(self, clients: List[str]):
        super().__init__()
        self.clients = clients

    def run(self) -> Generator[EventExpression, None, None]:

        for client in self.clients:

            self.context.ports[client].tx_output("Start entanglement")
            in_port = self.context.ports[client]
            yield self.await_port_input(in_port)
            print(f"{ns.sim_time()} ns: Server receives from {client}: {in_port.rx_input().items[0]}")

            egp = self.context.egp[client]

            # create request
            request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[client], number=1)
            egp.put(request)

            # Await request completion
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            result = self.context.node.qdevice.measure(received_qubit_mem_pos)[0]
            # TODO important to discard qubits otherwise memory gets full and program gets frozen
            # TODO Look into fix possibility of getting frozen situation due to memory full
            self.context.node.qdevice.discard(received_qubit_mem_pos)

            print(f"{ns.sim_time()} ns: Server Created EPR with {client} and measures {result}")


class ClientProtocol(BlueprintProtocol):
    def __init__(self, server_name: str):
        super().__init__()
        self.server_name = server_name

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.server_name]

        in_port = self.context.ports[self.server_name]
        yield self.await_port_input(in_port)
        print(f"{ns.sim_time()} ns: {self.context.node.name} receives from {self.server_name}: {in_port.rx_input().items[0]}")
        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.server_name]))
        self.context.ports[self.server_name].tx_output("Ready to start entanglement")

        qdevice = self.context.node.qdevice

        # Wait for a signal from the EGP.
        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        received_qubit_mem_pos = response.logical_qubit_id

        result = qdevice.measure(positions=[received_qubit_mem_pos])[0]
        qdevice.discard(received_qubit_mem_pos)
        print(f"{ns.sim_time()} ns: {self.context.node.name} measures {result}")
