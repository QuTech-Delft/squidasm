from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.classical_communication.socket import Socket
from netsquid.components.component import Port
from netsquid.protocols import NodeProtocol

if TYPE_CHECKING:
    from netqasm.sdk.config import LogConfig

from pydynaa import EventExpression, EventType

NewClasMsgEvent: EventType = EventType(
    "NewClasMsgEvent",
    "A new classical message from another peer has arrived on the Host",
)


class NetSquidSocket(Socket):
    def __init__(
        self,
        app_name: str,
        remote_app_name: str,
        protocol: NodeProtocol,
        port: Port,
        socket_id: int = 0,
    ):
        """Socket used to communicate classical data between applications."""
        super().__init__(
            app_name=app_name, remote_app_name=remote_app_name, socket_id=socket_id
        )
        self._protocol = protocol
        self._port = port

    def send(self, msg: str) -> None:
        """Sends a message to the remote node."""
        self._port.tx_output(msg)

    def recv(
        self,
    ) -> Generator[EventExpression, None, str]:
        """Receive a message from the remote node."""
        # yield self._protocol.await_port_input(self._port)
        # msg = self._port.rx_input().items[0]
        # assert isinstance(msg, str)
        # return msg
        if len(self._protocol._listener._buffer) == 0:
            yield EventExpression(
                source=self._protocol._listener, event_type=NewClasMsgEvent
            )
        return self._protocol._listener._buffer.pop(0)
