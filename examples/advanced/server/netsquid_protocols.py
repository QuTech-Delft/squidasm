"""
DISCLAIMER
============

This file creates various Netsquid Protocols in order to create listeners for each classical socket
 and other functionalities.
In a setting where one runs an application on hardware, one would, for example,
 start and use a thread for each listener.
But in SquidASM one can not create a functional application in the same fashion
 due the underlying discrete event simulator, Netsquid.
In this file, Netsquid Protocols have been created, but as these do not translate to hardware,
 any application written using them will require a larger translation to be compatible with hardware.
"""

from logging import Logger
from typing import Generator, Tuple

from netqasm.sdk.classical_communication.socket import Socket
from netsquid.protocols import Protocol

from squidasm.sim.stack.program import ProgramContext


class SleepingProtocol(Protocol):
    """Netsquid protocol to support waiting or sleeping in a Program."""

    def sleep(self, duration=0, end_time=0):
        """
        Sleep for a certain duration or until a certain end time.
        Specify either duration or end time, but not both.
        Requires usage of `yield from` before method call to function.

        :param duration: Time to sleep in nanoseconds.
        :param end_time: Simulation time to sleep to in nanoseconds.
        """
        yield self.await_timer(duration=duration, end_time=end_time)


class QueueProtocol(Protocol):
    """Netsquid protocol for a queue, that supports waiting for a new item, when the queue is empty."""

    QUEUE_STATUS_CHANGE_SIGNAL = "Queue has been updated"

    def __init__(self):
        self._queue = []
        self.add_signal(self.QUEUE_STATUS_CHANGE_SIGNAL)

    def push(self, msg_source: str, msg: str):
        """
        Put a new item on the queue.

        :param msg_source: Source of the message.
        :param msg: The message.
        """
        self._queue.append((msg_source, msg))
        self.send_signal(self.QUEUE_STATUS_CHANGE_SIGNAL)

    def pop(self) -> Generator[None, None, Tuple[str, str]]:
        """
        Take an item of the queue. Waits for a new item if the queue is empty.

        :return: A tuple with the source of the message and the message.
        """
        if len(self._queue) == 0:
            yield self.await_signal(sender=self, signal_label=self.QUEUE_STATUS_CHANGE_SIGNAL)  # fmt: skip
        return self._queue.pop()


class CSocketListener(Protocol):
    """Netsquid protocol that listens to messages on a CSocket and forwards them to the QueueProtocol."""

    def __init__(
        self,
        context: ProgramContext,
        peer_name: str,
        queue_protocol: QueueProtocol,
        logger: Logger,
    ):
        """
        :param context:  ProgramContext of the current program.
        :param peer_name: Name of the remote node this Listener should listen to.
        :param queue_protocol: The QueueProtocol where messages are forwarded to.
        :param logger: A Logger.
        """
        self._context = context
        self._peer_name = peer_name
        self._queue_protocol = queue_protocol
        self.logger = logger.getChild(f"PortListener({peer_name})")

    def run(self):
        csocket: Socket = self._context.csockets[self._peer_name]
        while True:
            message = yield from csocket.recv()
            self._queue_protocol.push(self._peer_name, str(message))
            self.logger.info(f"Received message: {message}")
