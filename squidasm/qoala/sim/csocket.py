from __future__ import annotations

from typing import Generator

from pydynaa import EventExpression
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.message import Message


class ClassicalSocket:
    """Wrapper around classical ports"""

    def __init__(self, host: HostInterface, remote_name: str):
        self._host = host
        self._remote_name = remote_name

    def send(self, msg: Message) -> None:
        """Send a message to the remote node."""
        self._host.send_peer_msg(self._remote_name, msg)

    def recv(self) -> Generator[EventExpression, None, Message]:
        msg = yield from self._host.receive_peer_msg(self._remote_name)
        return msg

    def send_str(self, msg: str) -> None:
        self.send(Message(content=msg))

    def recv_str(self) -> Generator[EventExpression, None, str]:
        msg = yield from self.recv()
        assert isinstance(msg.content, str)
        return msg.content

    def send_int(self, value: int) -> None:
        self.send(Message(content=value))

    def recv_int(self) -> Generator[EventExpression, None, int]:
        msg = yield from self.recv()
        assert isinstance(msg.content, int)
        return msg.content

    def send_float(self, value: float) -> None:
        self.send(Message(content=value))

    def recv_float(self) -> Generator[EventExpression, None, float]:
        msg = yield from self.recv()
        assert isinstance(msg.content, float)
        return msg.content
