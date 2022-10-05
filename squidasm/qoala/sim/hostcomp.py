from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import StopAppMessage, SubroutineMessage
from netqasm.lang.operand import Register
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang import iqoala
from squidasm.qoala.lang.iqoala import IqoalaProgram
from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.runtime.program import BatchResult, ProgramContext, ProgramInstance
from squidasm.qoala.sim.common import ComponentProtocol, PortListener
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostprocessor import HostProcessor, IqoalaProcess
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG
from squidasm.qoala.sim.util import default_nv_unit_module


class HostComponent(Component):
    """NetSquid component representing a Host.

    Subcomponent of a ProcNodeComponent.

    This is a static container for Host-related components and ports. Behavior
    of a Host is modeled in the `Host` class, which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node, global_env: GlobalEnvironment) -> None:
        super().__init__(f"{node.name}_host")

        self._peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._peer_out_ports: Dict[str, str] = {}  # peer name -> port name

        for node in global_env.get_nodes().values():
            port_in_name = f"peer_{node.name}_in"
            port_out_name = f"peer_{node.name}_out"
            self._peer_in_ports[node.name] = port_in_name
            self._peer_out_ports[node.name] = port_out_name

        self.add_ports(self._peer_in_ports.values())
        self.add_ports(self._peer_out_ports.values())

        self.add_ports(["qnos_in", "qnos_out"])

    @property
    def qnos_in_port(self) -> Port:
        return self.ports["qnos_in"]

    @property
    def qnos_out_port(self) -> Port:
        return self.ports["qnos_out"]

    def peer_in_port(self, name: str) -> Port:
        port_name = self._peer_in_ports[name]
        return self.ports[port_name]

    def peer_out_port(self, name: str) -> Port:
        port_name = self._peer_out_ports[name]
        return self.ports[port_name]
