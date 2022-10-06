from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Generator, List, Optional

import netsquid as ns
from netqasm.sdk.build_epr import (
    SER_CREATE_IDX_NUMBER,
    SER_CREATE_IDX_TYPE,
    SER_RESPONSE_KEEP_IDX_BELL_STATE,
    SER_RESPONSE_KEEP_IDX_GOODNESS,
    SER_RESPONSE_KEEP_LEN,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME,
    SER_RESPONSE_MEASURE_LEN,
)
from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node
from netsquid.qubits.ketstates import BellIndex
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from qlink_interface import (
    ReqCreateAndKeep,
    ReqCreateBase,
    ReqMeasureDirectly,
    ReqReceive,
    ResCreateAndKeep,
    ResMeasureDirectly,
)
from qlink_interface.interface import ReqRemoteStatePrep

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.common import (
    AllocError,
    ComponentProtocol,
    NetstackBreakpointCreateRequest,
    NetstackBreakpointReceiveRequest,
    NetstackCreateRequest,
    NetstackReceiveRequest,
    PhysicalQuantumMemory,
    PortListener,
)
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.memory import ProgramMemory
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.signals import (
    SIGNAL_MEMORY_FREED,
    SIGNAL_PEER_NSTK_MSG,
    SIGNAL_PROC_NSTK_MSG,
)

if TYPE_CHECKING:
    from squidasm.qoala.sim.qnos import Qnos


class NetstackInterface(ComponentProtocol):
    """NetSquid protocol representing the QNodeOS network stack."""

    def __init__(self, comp: NetstackComponent, local_env: LocalEnvironment) -> None:
        """Network stack protocol constructor. Typically created indirectly through
        constructing a `Qnos` instance.

        :param comp: NetSquid component representing the network stack
        :param qnos: `Qnos` protocol that owns this protocol
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp

        self._local_env = local_env

        self.add_listener(
            "processor",
            PortListener(self._comp.qnos_in_port, SIGNAL_PROC_NSTK_MSG),
        )
        for peer in self._local_env.get_all_node_names():
            self.add_listener(
                f"peer_{peer}",
                PortListener(
                    self._comp.peer_in_port(peer), f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
                ),
            )

    def _send_qnos_msg(self, msg: str) -> None:
        """Send a message to the processor."""
        self._comp.qnos_out_port.tx_output(msg)

    def _receive_qnos_msg(self) -> Generator[EventExpression, None, str]:
        """Receive a message from the processor. Block until there is at least one
        message."""
        return (yield from self._receive_msg("qnos", SIGNAL_PROC_NSTK_MSG))

    def _send_peer_msg(self, peer: str, msg: str) -> None:
        """Send a message to the network stack of the other node.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        self._comp.peer_out_port(peer).tx_output(msg)

    def _receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, str]:
        """Receive a message from the network stack of the other node. Block until
        there is at least one message.

        NOTE: for now we assume there is only one other node, which is 'the' peer."""
        return (
            yield from self._receive_msg(
                f"peer_{peer}", f"{SIGNAL_PEER_NSTK_MSG}_{peer}"
            )
        )
