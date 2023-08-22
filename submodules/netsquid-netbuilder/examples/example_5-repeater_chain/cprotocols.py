from typing import Generator

import netsquid as ns
from netsquid_netbuilder.protocol_base import BlueprintProtocol

from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        socket = self.context.sockets[self.PEER]

        message = yield from socket.recv()

        print(f"{ns.sim_time()} ns: Alice receives: {message}")


class BobProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self):
        socket = self.context.sockets[self.PEER]

        msg = "Hello"
        socket.send(msg)