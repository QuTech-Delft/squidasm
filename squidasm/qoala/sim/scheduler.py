from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from netqasm.lang.operand import Register, Template
from netsquid.components.component import Component
from netsquid.nodes import Node
from netsquid.protocols import Protocol

from squidasm.qoala.lang import iqoala
from squidasm.qoala.runtime.program import BatchResult, ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.netstack import Netstack
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qnos import Qnos


@dataclass
class HostTask:
    no_more_tasks: bool
    pid: int
    instr_idx: int


class SchedulerComponent(Component):
    """NetSquid component representing a Scheduler."""

    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_scheduler")
        self._node = node

    @property
    def node(self) -> Node:
        return self._node


class ProgramSchedule:
    def __init__(self, program: iqoala.IqoalaProgram) -> None:
        self._program: iqoala.IqoalaProgram = program
        self._schedule: Dict[int, int] = {}  # instr index -> time


class Scheduler(Protocol):
    def __init__(
        self, node_name: str, host: Host, qnos: Qnos, netstack: Netstack
    ) -> None:
        self._node_name = node_name

        self._host = host
        self._qnos = qnos
        self._netstack = netstack

        self._queued_programs: Dict[int, ProgramInstance] = {}
        self._program_counter: int = 0
        self._batch_counter: int = 0
        self._processes: Dict[int, IqoalaProcess] = {}

        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({node_name})"
        )

        # batch ID -> list of program instance IDs
        self._batches: Dict[int, List[int]]

        self._csockets: Dict[int, Dict[str, ClassicalSocket]] = {}

        self._program_results: Dict[int, BatchResult] = {}

        self._local_schedule: Optional[Schedule] = None

    def install_schedule(self, schedule: Schedule):
        self._local_schedule = schedule

    def next_host_task(self) -> HostTask:
        pass

    def initialize(self, process: IqoalaProcess) -> None:
        host_mem = process.prog_memory.host_mem
        inputs = process.prog_instance.inputs
        for name, value in inputs.values.items():
            host_mem.write(name, value)

        for req in process.requests.values():
            # TODO: support for other request parameters being templates?
            remote_id = req.request.remote_id
            if isinstance(remote_id, Template):
                req.request.remote_id = inputs.values[remote_id.name]
