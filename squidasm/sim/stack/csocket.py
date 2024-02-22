from __future__ import annotations

from typing import Generator

import netsquid_driver.classical_socket_service as netsquid_classical_socket_service
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.classical_communication.socket import Socket

from pydynaa import EventExpression


class ClassicalSocket(Socket):
    """Classical socket, used for simulating classical data exchange between programs."""

    def __init__(
        self,
        netsquid_socket: netsquid_classical_socket_service.ClassicalSocket,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
    ):
        super().__init__(
            app_name=app_name, remote_app_name=remote_app_name, socket_id=socket_id
        )
        self.netsquid_socket = netsquid_socket

    def send(self, msg: str) -> None:
        """Sends a string message to the remote node."""
        self.netsquid_socket.send(msg)

    def recv(self, **kwargs) -> Generator[EventExpression, None, str]:
        """Receive a string message to the remote node."""
        return (yield from self.netsquid_socket.recv())

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
        """Send a structured message to the remote node."""
        self.send(msg)

    def recv_structured(
        self, **kwargs
    ) -> Generator[EventExpression, None, StructuredMessage]:
        """Receive a structured message to the remote node."""
        value = yield from self.recv()
        return value

    def recv_silent(self, **kwargs) -> str:
        raise NotImplementedError

    def send_silent(self, msg: str) -> None:
        raise NotImplementedError
