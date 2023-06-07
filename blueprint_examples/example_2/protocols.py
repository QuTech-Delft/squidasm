from typing import Generator
import netsquid as ns
from netsquid.protocols import Protocol, Signals

from blueprint.network import ProtocolContext
from pydynaa import EventExpression


class AliceProtocol(Protocol):
    PEER = "Bob"

    def __init__(self, context: ProtocolContext):
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:
        msg = "Hello from Alice"
        print(f"{ns.sim_time()} ns: Alice sends: {msg}")
        self.context.ports[self.PEER].tx_output(msg)
        yield self.await_timer(10)

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()


class BobProtocol(Protocol):
    PEER = "Alice"

    def __init__(self, context: ProtocolContext):
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:

        port = self.context.ports[self.PEER]
        yield self.await_port_input(port)
        message = port.rx_input()
        print(f"{ns.sim_time()} ns: Bob receives: {message.items[0]}")

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
