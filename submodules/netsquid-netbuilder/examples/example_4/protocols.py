from typing import Generator

import netsquid as ns
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from netsquid_netbuilder.protocol_base import BlueprintProtocol
from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    def __init__(self, peer: str, num_epr_pairs: int):
        super().__init__()
        self.peer = peer
        self.num_epr_pairs = num_epr_pairs

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.peer]
        egp = self.context.egp[self.peer]
        qdevice = self.context.node.qdevice

        for i in range(self.num_epr_pairs):
            yield self.await_port_input(port)
            message = port.rx_input()
            print(f"{ns.sim_time(ns.MILLISECOND)} ms: {self.context.node.name} receives: {message.items[0]}")

            request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.peer], number=1)
            egp.put(request)

            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id
            result = qdevice.measure(received_qubit_mem_pos)[0]
            qdevice.discard(received_qubit_mem_pos)

            print(f"{ns.sim_time(ns.MILLISECOND)} ms: pair: {i} {self.context.node.name} Created EPR with {self.peer} and measures {result}")


class BobProtocol(BlueprintProtocol):
    def __init__(self, peer: str, num_epr_pairs: int):
        super().__init__()
        self.peer = peer
        self.num_epr_pairs = num_epr_pairs

    def run(self) -> Generator[EventExpression, None, None]:
        egp = self.context.egp[self.peer]
        port = self.context.ports[self.peer]
        qdevice = self.context.node.qdevice

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.peer]))

        for i in range(self.num_epr_pairs):
            msg = "Ready to start entanglement"
            port.tx_output(msg)
            print(f"{ns.sim_time(ns.MILLISECOND)} ms: {self.context.node.name} sends: {msg}")

            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
            received_qubit_mem_pos = response.logical_qubit_id

            result = qdevice.measure(positions=[received_qubit_mem_pos])[0]
            qdevice.discard(received_qubit_mem_pos)
            print(f"{ns.sim_time(ns.MILLISECOND)} ms: pair: {i} {self.context.node.name} Created EPR with {self.peer} and measures {result}")

