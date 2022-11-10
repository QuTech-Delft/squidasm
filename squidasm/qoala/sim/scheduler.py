from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from netsquid.components.component import Component
from netsquid.nodes import Node
from netsquid.protocols import Protocol

from squidasm.qoala.lang import iqoala
from squidasm.qoala.runtime.program import BatchResult, ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.process import IqoalaProcess


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
    def __init__(self, node_name: str) -> None:
        self._node_name = node_name
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
