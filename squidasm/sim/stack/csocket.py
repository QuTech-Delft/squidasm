from __future__ import annotations

from typing import TYPE_CHECKING, Generator

from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.classical_communication.socket import Socket

from pydynaa import EventExpression

if TYPE_CHECKING:
    from squidasm.sim.stack.host import Host


class ClassicalSocket(Socket):
    def __init__(
        self,
        host: Host,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
    ):
        """Socket used to communicate classical data between applications."""
        super().__init__(
            app_name=app_name, remote_app_name=remote_app_name, socket_id=socket_id
        )
        self._host = host

    def send(self, msg: str) -> None:
        """Sends a message to the remote node."""
        self._host.send_peer_msg(msg)

    def recv(self) -> Generator[EventExpression, None, str]:
        return (yield from self._host.receive_peer_msg())

    def send_int(self, value: int) -> None:
        self.send(str(value))

    def recv_int(self) -> Generator[EventExpression, None, int]:
        value = yield from self.recv()
        return int(value)

    def send_float(self, value: float) -> None:
        self.send(str(value))

    def recv_float(self) -> Generator[EventExpression, None, float]:
        value = yield from self.recv()
        return float(value)

    def send_structured(self, msg: StructuredMessage) -> None:
        self.send(msg)

    def recv_structured(self) -> Generator[EventExpression, None, StructuredMessage]:
        value = yield from self.recv()
        return value
