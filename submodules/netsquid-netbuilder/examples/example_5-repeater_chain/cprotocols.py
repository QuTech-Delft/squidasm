from typing import Generator

import netsquid as ns
import netsquid.qubits.qubitapi
from netsquid.components import INSTR_X, QuantumProcessor
from netsquid.components.component import Qubit

from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.PEER]

        yield self.await_port_input(port)
        message = port.rx_input()
        print(f"{ns.sim_time()} ns: Alice receives: {message.items[0]}")


class BobProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self):
        port = self.context.ports[self.PEER]

        msg = "Hello"
        port.tx_output(msg)
        print(f"{ns.sim_time()} ns: Bob sends: {msg}")

