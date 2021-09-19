from __future__ import annotations

from typing import TYPE_CHECKING, Generator

from netqasm.sdk.classical_communication.socket import Socket
from netsquid.components.component import Port

from pydynaa import EventExpression, EventType
from squidasm.run.singlethread.context import NetSquidContext

if TYPE_CHECKING:
    from squidasm.run.singlethread.protocols import HostProtocol

NewClasMsgEvent: EventType = EventType(
    "NewClasMsgEvent",
    "A new classical message from another peer has arrived on the Host",
)


class NetSquidSocket(Socket):
    def __init__(
        self,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
    ):
        """Socket used to communicate classical data between applications."""
        super().__init__(
            app_name=app_name, remote_app_name=remote_app_name, socket_id=socket_id
        )
        self._protocol: HostProtocol = NetSquidContext.get_protocols()[app_name]
        self._port: Port = self._protocol.peer_port

    def send(self, msg: str) -> None:
        """Sends a message to the remote node."""
        self._port.tx_output(msg)

    def recv(
        self,
    ) -> Generator[EventExpression, None, str]:
        """Receive a message from the remote node."""

        if len(self._protocol.peer_listener.buffer) == 0:
            yield EventExpression(
                source=self._protocol.peer_listener, event_type=NewClasMsgEvent
            )
        return self._protocol.peer_listener.buffer.pop(0)
