from __future__ import annotations

from typing import Generator

from qlink_interface.interface import (
    ReqCreateBase,
    ResCreate,
    ResCreateAndKeep,
    ResMeasureDirectly,
)

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.common import ComponentProtocol, PortListener
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.qdevice import QDevice
from squidasm.qoala.sim.signals import (
    SIGNAL_MEMORY_FREED,
    SIGNAL_PEER_NSTK_MSG,
    SIGNAL_PROC_NSTK_MSG,
)


class NetstackInterface(ComponentProtocol):
    """NetSquid protocol representing the QNodeOS network stack."""

    def __init__(
        self,
        comp: NetstackComponent,
        local_env: LocalEnvironment,
        qdevice: QDevice,
        memmgr: MemoryManager,
        egpmgr: EgpManager,
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
        self._memmgr = memmgr
        self._egpmgr = egpmgr

        self.add_listener(
            "qnos",
            PortListener(self._comp.qnos_in_port, SIGNAL_PROC_NSTK_MSG),
        )

        self.add_listener(
            "qnos_mem",
            PortListener(self._comp.qnos_mem_in_port, SIGNAL_MEMORY_FREED),
        )

        for peer in self._local_env.get_all_other_node_names():
            self.add_listener(
                f"peer_{peer}",
                PortListener(
                    self._comp.peer_in_port(peer), f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
                ),
            )

    def send_qnos_msg(self, msg: Message) -> None:
        """Send a message to the processor."""
        self._comp.qnos_out_port.tx_output(msg)

    def receive_qnos_msg(self) -> Generator[EventExpression, None, Message]:
        """Receive a message from the processor. Block until there is at least one
        message."""
        return (yield from self._receive_msg("qnos", SIGNAL_PROC_NSTK_MSG))

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        """Send a message to the network stack of the other node.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        self._comp.peer_out_port(peer).tx_output(msg)

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        """Receive a message from the network stack of the other node. Block until
        there is at least one message.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        return (
            yield from self._receive_msg(
                f"peer_{peer}", f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
            )
        )

    def put_request(self, remote_id: int, request: ReqCreateBase) -> None:
        egp = self._egpmgr.get_egp(remote_id)
        egp.put(request)

    def await_result_create_keep(
        self, remote_id: int
    ) -> Generator[EventExpression, None, ResCreateAndKeep]:
        egp = self._egpmgr.get_egp(remote_id)
        yield self.await_signal(
            sender=egp,
            signal_label=ResCreateAndKeep.__name__,
        )
        result: ResCreateAndKeep = egp.get_signal_result(
            ResCreateAndKeep.__name__, receiver=self
        )
        return result

    def await_result_measure_directly(
        self, remote_id: int
    ) -> Generator[EventExpression, None, ResMeasureDirectly]:
        egp = self._egpmgr.get_egp(remote_id)
        yield self.await_signal(
            sender=egp,
            signal_label=ResMeasureDirectly.__name__,
        )
        result: ResMeasureDirectly = egp.get_signal_result(
            ResMeasureDirectly.__name__, receiver=self
        )
        return result

    def await_memory_freed_signal(
        self, pid: int, virt_id: int
    ) -> Generator[EventExpression, None, None]:
        # TODO: use pid and virt_id?
        yield from self._receive_msg("qnos_mem", SIGNAL_MEMORY_FREED)

    @property
    def qdevice(self) -> QDevice:
        return self._qdevice

    @property
    def memmgr(self) -> MemoryManager:
        return self._memmgr

    @property
    def egpmgr(self) -> EgpManager:
        return self._egpmgr

    def remote_id_to_peer_name(self, remote_id: int) -> str:
        node_info = self._local_env.get_global_env().get_nodes()[remote_id]
        # TODO figure out why mypy does not like this
        return node_info.name  # type: ignore
