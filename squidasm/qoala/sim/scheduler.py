from __future__ import annotations

from selectors import EVENT_WRITE
from typing import TYPE_CHECKING, Dict, Generator, List, Optional

import netsquid as ns
from netqasm.lang.subroutine import Subroutine
from netsquid.components.component import Component
from netsquid.nodes import Node

from pydynaa import Entity, EventExpression, EventType
from squidasm.qoala.lang import lhr
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.common import ComponentProtocol, ProgramResult
from squidasm.qoala.sim.connection import QnosConnection
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.host import Host

if TYPE_CHECKING:
    from squidasm.qoala.sim.qnos import Qnos


class SchedulerComponent(Component):
    """NetSquid component representing a Scheduler."""

    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_scheduler")
        self._node = node

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


EVENT_WAIT = EventType("SCHEDULER_WAIT", "scheduler wait")


class Scheduler(ComponentProtocol, Entity):
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

        self._program_results: Dict[int, ProgramResult] = {}

        self._local_schedule: Optional[Schedule] = None

    def install_schedule(self, schedule: Schedule):
        self._local_schedule = schedule

    def wait_until_next_slot(self) -> Generator[EventExpression, None, None]:
        now = ns.sim_time()
        next_slot = self._local_schedule.next_slot(now)
        delta = next_slot - now
        self._logger.warning(f"next slot = {next_slot}")
        self._logger.warning(f"delta = {delta}")
        self._schedule_after(delta, EVENT_WAIT)
        event_expr = EventExpression(source=self, event_type=EVENT_WAIT)
        yield event_expr

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""

        # Run a single program as many times as requested.
        programs = list(self._queued_programs.items())
        if len(programs) == 0:
            return

        app_id, prog_instance = programs[0]

        assert isinstance(prog_instance.program, lhr.LhrProgram)

        for i in range(len(prog_instance.program.instructions)):
            if self._local_schedule is not None:
                yield from self.wait_until_next_slot()
            self._logger.warning(f"time: {ns.sim_time()}, executing instr #{i}")
            yield from self._host.run_lhr_instr(app_id, i)

        result = self._host.program_end(app_id)
        self._program_results[app_id] = result

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

    def get_results(self) -> Dict[int, ProgramResult]:
        return self._program_results
