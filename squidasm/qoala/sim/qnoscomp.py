from __future__ import annotations

from typing import Dict, Optional, Tuple

from netqasm.lang.subroutine import Subroutine
from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.common import NVPhysicalQuantumMemory, PhysicalQuantumMemory
from squidasm.qoala.sim.memory import ProgramMemory, QuantumMemory, SharedMemory
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.qnosprocessor import (
    GenericProcessor,
    NVProcessor,
    Processor,
    ProcessorComponent,
)


class QnosComponent(Component):
    """NetSquid component representing a QNodeOS instance.

    Subcomponent of a ProcNodeComponent.

    This is a static container for QNodeOS-related components and ports.
    Behavior of a QNodeOS instance is modeled in the `Qnos` class,
    which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node, global_env: GlobalEnvironment) -> None:
        super().__init__(name=f"{node.name}_qnos")
        self._node = node

        # Ports for communicating with Host
        self.add_ports(["host_out", "host_in"])
        self.add_ports(["nstk_out", "nstk_in"])

    @property
    def host_in_port(self) -> Port:
        return self.ports["host_in"]

    @property
    def netstack_out_port(self) -> Port:
        return self.ports["nstk_out"]

    @property
    def netstack_in_port(self) -> Port:
        return self.ports["nstk_in"]

    @property
    def host_out_port(self) -> Port:
        return self.ports["host_out"]

    @property
    def node(self) -> Node:
        return self._node
