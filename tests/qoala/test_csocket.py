from __future__ import annotations

from typing import Generator, List, Optional, Tuple

from pydynaa import EventExpression
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.message import Message
from squidasm.util.tests import yield_from


class MockHostInterface(HostInterface):
    def __init__(self) -> None:
        self.remote: Optional[MockHostInterface] = None
        self.messages: List[Message] = []

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        assert self.remote is not None
        self.remote.messages.append(msg)

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        return self.messages.pop()
        yield  # to make it behave as a generator


def setup_alice_bob() -> Tuple[ClassicalSocket, ClassicalSocket]:
    alice = MockHostInterface()
    bob = MockHostInterface()
    alice.remote = bob
    bob.remote = alice

    return (ClassicalSocket(alice, "bob"), ClassicalSocket(bob, "alice"))


def test_send_str():
    alice, bob = setup_alice_bob()

    alice.send("hello")
    msg = yield_from(bob.recv())
    assert msg == "hello"


def test_send_int():
    alice, bob = setup_alice_bob()

    alice.send_int(3)
    msg = yield_from(bob.recv_int())
    assert msg == 3


def test_send_float():
    alice, bob = setup_alice_bob()

    alice.send_float(3.14)
    msg = yield_from(bob.recv_float())
    assert msg == 3.14


if __name__ == "__main__":
    test_send_str()
