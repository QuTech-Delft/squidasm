from __future__ import annotations

from typing import Generator

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.common import ComponentProtocol, PortListener
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG


class HostInterface(ComponentProtocol):
    """NetSquid protocol representing a Host."""

    def __init__(
        self,
        comp: HostComponent,
        local_env: LocalEnvironment,
    ) -> None:
        """Host protocol constructor.

        :param comp: NetSquid component representing the Host
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp

        self._local_env = local_env

        self.add_listener(
            "qnos",
            PortListener(self._comp.ports["qnos_in"], SIGNAL_HAND_HOST_MSG),
        )
        for peer in self._local_env.get_all_node_names():
            self.add_listener(
                f"peer_{peer}",
                PortListener(
                    self._comp.peer_in_port(peer), f"{SIGNAL_HOST_HOST_MSG}_{peer}"
                ),
            )

    def send_qnos_msg(self, msg: Message) -> None:
        self._comp.qnos_out_port.tx_output(msg)

    def receive_qnos_msg(self) -> Generator[EventExpression, None, Message]:
        return (yield from self._receive_msg("qnos", SIGNAL_HAND_HOST_MSG))

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        self._comp.peer_out_port(peer).tx_output(msg)

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        return (
            yield from self._receive_msg(
                f"peer_{peer}", f"{SIGNAL_HOST_HOST_MSG}_{peer}"
            )
        )
