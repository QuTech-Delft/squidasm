from __future__ import annotations

from typing import Generator

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.common import ComponentProtocol, PortListener
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.qdevice import QDevice
from squidasm.qoala.sim.signals import SIGNAL_PEER_NSTK_MSG, SIGNAL_PROC_NSTK_MSG


class NetstackInterface(ComponentProtocol):
    """NetSquid protocol representing the QNodeOS network stack."""

    def __init__(
        self,
        comp: NetstackComponent,
        local_env: LocalEnvironment,
        qdevice: QDevice,
        memmgr: MemoryManager,
    ) -> None:
        """Network stack protocol constructor. Typically created indirectly through
        constructing a `Qnos` instance.

        :param comp: NetSquid component representing the network stack
        :param qnos: `Qnos` protocol that owns this protocol
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._qdevice = qdevice
        self._local_env = local_env

        self.add_listener(
            "processor",
            PortListener(self._comp.qnos_in_port, SIGNAL_PROC_NSTK_MSG),
        )
        for peer in self._local_env.get_all_other_node_names():
            self.add_listener(
                f"peer_{peer}",
                PortListener(
                    self._comp.peer_in_port(peer), f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
                ),
            )

    def _send_qnos_msg(self, msg: Message) -> None:
        """Send a message to the processor."""
        self._comp.qnos_out_port.tx_output(msg)

    def _receive_qnos_msg(self) -> Generator[EventExpression, None, Message]:
        """Receive a message from the processor. Block until there is at least one
        message."""
        return (yield from self._receive_msg("qnos", SIGNAL_PROC_NSTK_MSG))

    def _send_peer_msg(self, peer: str, msg: Message) -> None:
        """Send a message to the network stack of the other node.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        self._comp.peer_out_port(peer).tx_output(msg)

    def _receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        """Receive a message from the network stack of the other node. Block until
        there is at least one message.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        return (
            yield from self._receive_msg(
                f"peer_{peer}", f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
            )
        )

    @property
    def qdevice(self) -> QDevice:
        return self._qdevice

    @property
    def memmgr(self) -> MemoryManager:
        return self._memmgr
