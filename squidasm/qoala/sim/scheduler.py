from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

import netsquid as ns
from netqasm.lang.subroutine import Subroutine
from netsquid.components.component import Component
from netsquid.nodes import Node

from pydynaa import Entity, EventExpression, EventType
from squidasm.qoala.lang import iqoala
from squidasm.qoala.lang.iqoala import IqoalaProgram
from squidasm.qoala.runtime.program import BatchInfo, BatchResult, ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.common import ComponentProtocol
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.host import Host, IqoalaProcess
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.util import default_nv_unit_module

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
    def __init__(self, pid: int) -> None:
        self._id = pid
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
    def __init__(self, program: iqoala.IqoalaProgram) -> None:
        self._program: iqoala.IqoalaProgram = program
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
        self._batch_counter: int = 0
        self._processes: Dict[int, IqoalaProcess] = {}

        # batch ID -> list of program instance IDs
        self._batches: Dict[int, List[int]]

        self._csockets: Dict[int, Dict[str, ClassicalSocket]] = {}

        self._program_results: Dict[int, BatchResult] = {}

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

        for program in programs:
            pid, prog_instance = program

            assert isinstance(prog_instance.program, iqoala.IqoalaProgram)

            for i in range(len(prog_instance.program.instructions)):
                if self._local_schedule is not None:
                    yield from self.wait_until_next_slot()
                self._logger.warning(f"time: {ns.sim_time()}, executing instr #{i}")
                yield from self._host.run_iqoala_instr(pid, i)

            result = self._host.program_end(pid)
            self._program_results[pid] = result

    def new_pid(self) -> int:
        self._program_counter += 1
        return self._program_counter

    def new_batch_id(self) -> int:
        self._batch_counter += 1
        return self._batch_counter

    def submit_batch(self, info: BatchInfo) -> int:
        batch_id = self.new_batch_id()
        instances = [
            self.new_program_instance(info.program, info.inputs[i])
            for i in range(info.num_iterations)
        ]
        self._batches[batch_id] = [inst.pid for inst in instances]
        return batch_id

    def run_batch(self, batch_id: int) -> None:
        # Create processes for each of the instances in the batch.
        # The scheduler will automatically pick up these processes.
        for pid in self._batches[batch_id]:
            self.create_process(pid)

    def new_program_instance(
        self, program: IqoalaProgram, inputs: Dict[str, Any]
    ) -> ProgramInstance:
        pid = self.new_pid()
        self._csockets[pid] = {}
        global_env = self._host.local_env.get_global_env()

        for i, remote_name in enumerate(program.meta.csockets):
            remote_id = global_env.get_node_id(remote_name)
            self.open_csocket(pid, remote_name)

        for i, remote_name in enumerate(program.meta.epr_sockets):
            remote_id = None

            # TODO: rewrite
            nodes = global_env.get_nodes()
            for id, info in nodes.items():
                if info.name == remote_name:
                    remote_id = id

            assert remote_id is not None
            self._qnos.handler.open_epr_socket(pid, i, remote_id)

        instance = ProgramInstance(pid, program, inputs)
        self._queued_programs[pid] = instance
        return instance

    def create_process(self, pid: int) -> None:
        program_memory = ProgramMemory(pid, default_nv_unit_module())
        instance = self._queued_programs[pid]

        process = IqoalaProcess(self, instance, program_memory, self._csockets[pid])
        self._processes[pid] = process

        self._qnos.handler.init_new_app(pid)

    def schedule_process(self, pid: int) -> Generator[EventExpression, None, None]:
        process = self._processes[pid]
        yield from self._host.processor.execute_next_instr(process)

    def open_csocket(self, pid: int, remote_name: str) -> None:
        assert pid in self._csockets
        self._csockets[pid][remote_name] = ClassicalSocket(self, remote_name)

    def get_results(self) -> Dict[int, BatchResult]:
        return self._program_results
