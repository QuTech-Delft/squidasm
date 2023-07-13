from __future__ import annotations

from typing import Generator

from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.classical_communication.socket import Socket
from netsquid.components import Port
from netsquid.protocols import Protocol

from pydynaa import EventExpression
from squidasm.sim.stack.common import PortListener
from squidasm.sim.stack.signals import SIGNAL_PEER_RECV_MSG


class ClassicalSocket(Socket, Protocol):
    """Classical socket, used for simulating classical data exchange between programs."""

    def __init__(
        self,
        port: Port,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
    ):
        super().__init__(
            app_name=app_name, remote_app_name=remote_app_name, socket_id=socket_id
        )
        self.port = port

        self.listener = PortListener(self.port, SIGNAL_PEER_RECV_MSG)

    def send(self, msg: str) -> None:
        """Sends a string message to the remote node."""
        self.port.tx_output(msg)

    def recv(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg(SIGNAL_PEER_RECV_MSG))

    def _receive_msg(
        self, wake_up_signal: str
    ) -> Generator[EventExpression, None, str]:
        if len(self.listener.buffer) == 0:
            yield self.await_signal(sender=self.listener, signal_label=wake_up_signal)
        return self.listener.buffer.pop(0)

    def send_int(self, value: int) -> None:
        """Send an integer value to the remote node."""
        self.send(str(value))

    def recv_int(self) -> Generator[EventExpression, None, int]:
        """Receive an integer value to the remote node."""
        value = yield from self.recv()
        return int(value)

    def send_float(self, value: float) -> None:
        """Send an float value to the remote node."""
        self.send(str(value))

    def recv_float(self) -> Generator[EventExpression, None, float]:
        """Receive an float value to the remote node."""
        value = yield from self.recv()
        return float(value)

    def send_structured(self, msg: StructuredMessage) -> None:
        """Send an structured message to the remote node."""
        self.send(msg)

    def recv_structured(self) -> Generator[EventExpression, None, StructuredMessage]:
        """Receive an structured message to the remote node."""
        value = yield from self.recv()
        return value

    def start(self):
        Protocol.start(self)
        self.listener.start()

    def stop(self):
        Protocol.stop(self)
        self.listener.stop()
