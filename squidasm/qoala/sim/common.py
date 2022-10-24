import logging
from dataclasses import dataclass
from typing import Dict, Generator, List

from netsquid.components.component import Component, Port
from netsquid.protocols import Protocol

from pydynaa import EventExpression
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.message import Message


class PortListener(Protocol):
    def __init__(self, port: Port, signal_label: str) -> None:
        self._buffer: List[Message] = []
        self._port: Port = port
        self._signal_label = signal_label
        self.add_signal(signal_label)

    @property
    def buffer(self) -> List[Message]:
        return self._buffer

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            # Wait for an event saying that there is new input.
            yield self.await_port_input(self._port)

            counter = 0
            # Read all inputs and count them.
            while True:
                input = self._port.rx_input()
                if input is None:
                    break
                self._buffer += input.items
                counter += 1
            # If there are n inputs, there have been n events, but we yielded only
            # on one of them so far. "Flush" these n-1 additional events:
            while counter > 1:
                yield self.await_port_input(self._port)
                counter -= 1

            # Only after having yielded on all current events, we can schedule a
            # notification event, so that its reactor can handle all inputs at once.
            self.send_signal(self._signal_label)


class ComponentProtocol(Protocol):
    def __init__(self, name: str, comp: Component) -> None:
        super().__init__(name)
        self._listeners: Dict[str, PortListener] = {}
        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({comp.name})"
        )

    def add_listener(self, name, listener: PortListener) -> None:
        self._listeners[name] = listener

    def _receive_msg(
        self, listener_name: str, wake_up_signal: str
    ) -> Generator[EventExpression, None, Message]:
        listener = self._listeners[listener_name]
        if len(listener.buffer) == 0:
            yield self.await_signal(sender=listener, signal_label=wake_up_signal)
        return listener.buffer.pop(0)

    def start(self) -> None:
        super().start()
        for listener in self._listeners.values():
            listener.start()

    def stop(self) -> None:
        for listener in self._listeners.values():
            listener.stop()
        super().stop()


@dataclass
class NetstackCreateRequest:
    pid: int
    remote_node_id: int
    epr_socket_id: int
    qubit_array_addr: int
    arg_array_addr: int
    result_array_addr: int


@dataclass
class NetstackReceiveRequest:
    pid: int
    remote_node_id: int
    epr_socket_id: int
    qubit_array_addr: int
    result_array_addr: int


@dataclass
class NetstackBreakpointCreateRequest:
    pid: int


@dataclass
class NetstackBreakpointReceiveRequest:
    pid: int
