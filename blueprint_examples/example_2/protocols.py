from typing import Generator

from netsquid.protocols import Protocol, Signals

from blueprint.network import ProtocolContext
from pydynaa import EventExpression


class AliceProtocol(Protocol):
    PEER = "Bob"

    def __init__(self, context: ProtocolContext):
        self.context = context
        self.add_signal(Signals.FINISHED)

    def run(self) -> Generator[EventExpression, None, None]:

        self.context.out_ports[self.PEER].tx_output("Hello from Alice")
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

        in_port = self.context.in_ports[self.PEER]
        yield self.await_port_input(in_port)
        message = in_port.rx_input()
        print(f"Bob receives: {message.items[0]}")

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
