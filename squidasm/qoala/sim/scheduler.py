from __future__ import annotations

import logging
from ctypes import Union
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import (
    InitNewAppMessage,
    Message,
    OpenEPRSocketMessage,
    StopAppMessage,
    SubroutineMessage,
    deserialize_host_msg,
)
from netqasm.lang.instr import flavour
from netqasm.lang.operand import Register
from netqasm.lang.parsing import deserialize as deser_subroutine
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang import lhr
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.runtime.program import ProgramContext, ProgramInstance, SdkProgram
from squidasm.qoala.sim.common import (
    AppMemory,
    ComponentProtocol,
    LogManager,
    PhysicalQuantumMemory,
    PortListener,
)
from squidasm.qoala.sim.connection import QnosConnection
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.host import Host, HostProgramContext
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.signals import (
    SIGNAL_HAND_HOST_MSG,
    SIGNAL_HOST_HAND_MSG,
    SIGNAL_HOST_HOST_MSG,
    SIGNAL_PROC_HAND_MSG,
)

if TYPE_CHECKING:
    from squidasm.qoala.sim.processor import ProcessorComponent
    from squidasm.qoala.sim.qnos import Qnos, QnosComponent


class SchedulerComponent(Component):
    """NetSquid component representing a Scheduler."""

    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_scheduler")
        self._node = node
        # self.add_ports(["proc_out", "proc_in"])
        # self.add_ports(["host_out", "host_in"])

    @property
    def node(self) -> Node:
        return self._node


class RunningQoalaProgram:
    def __init__(self, app_id: int) -> None:
        self._id = app_id
        self._pending_subroutines: List[Subroutine] = []

    def add_subroutine(self, subroutine: Subroutine) -> None:
        self._pending_subroutines.append(subroutine)

    def next_subroutine(self) -> Optional[Subroutine]:
        if len(self._pending_subroutines) > 0:
            return self._pending_subroutines.pop()
        return None

    @property
    def id(self) -> int:
        return self._id


class ProgramSchedule:
    def __init__(self, program: lhr.LhrProgram) -> None:
        self._program: lhr.LhrProgram = program
        self._schedule: Dict[int, int] = {}  # instr index -> time


class Schedule:
    def __init__(self) -> None:
        self._schedule: Dict[lhr.ClassicalLhrOp, int] = {}


class Scheduler(ComponentProtocol):
    """NetSquid protocol representing a Scheduler."""

    def __init__(
        self,
        comp: SchedulerComponent,
        host: Host,
        qnos: Qnos,
    ) -> None:
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._host = host
        self._qnos = qnos

        self._queued_programs: Dict[int, ProgramInstance] = {}
        self._program_counter: int = 0

        self._connections: Dict[int, QnosConnection] = {}

        self._csockets: Dict[int, Dict[str, ClassicalSocket]] = {}

        # Results of program runs so far.
        self._program_results: List[Dict[str, Any]] = []

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""

        # Run a single program as many times as requested.
        programs = list(self._queued_programs.items())
        if len(programs) == 0:
            return

        app_id, prog_instance = programs[0]

        assert isinstance(prog_instance.program, lhr.LhrProgram)

        yield from self._host.run_lhr_program(app_id)

    def init_new_program(self, program: ProgramInstance) -> int:
        app_id = self._program_counter
        self._program_counter += 1
        self._queued_programs[app_id] = program

        self._host.init_new_program(program, app_id)
        self._qnos.handler.init_new_app(app_id)

        # TODO rewrite
        global_env = self._host.local_env.get_global_env()

        for i, remote_name in enumerate(program.program.meta.csockets):
            remote_id = None

            # TODO: rewrite
            nodes = global_env.get_nodes()
            for id, info in nodes.items():
                if info.name == remote_name:
                    remote_id = id

            assert remote_id is not None
            self._host.open_csocket(app_id, remote_name)

        for i, remote_name in enumerate(program.program.meta.epr_sockets):
            remote_id = None

            # TODO: rewrite
            nodes = global_env.get_nodes()
            for id, info in nodes.items():
                if info.name == remote_name:
                    remote_id = id

            assert remote_id is not None
            self._qnos.handler.open_epr_socket(app_id, i, remote_id)

        return app_id
