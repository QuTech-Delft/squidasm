from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple, Type

import netsquid as ns
from netqasm.lang.instr.core import CreateEPRInstruction, RecvEPRInstruction
from netqasm.lang.operand import Template
from netsquid.components.component import Component
from netsquid.nodes import Node
from netsquid.protocols import Protocol

from pydynaa import EventExpression
from squidasm.qoala.lang import iqoala
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.runtime.program import (
    BatchInfo,
    BatchResult,
    ProgramBatch,
    ProgramInstance,
    ProgramResult,
)
from squidasm.qoala.runtime.schedule import (
    HostTask,
    NetstackTask,
    ProcessorType,
    ProgramTask,
    ProgramTaskList,
    QnosTask,
    Schedule,
    ScheduleEntry,
    SchedulerInput,
    SchedulerOutput,
    ScheduleSolver,
    ScheduleTime,
)
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.events import EVENT_WAIT
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.netstack import Netstack
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qnos import Qnos


class Scheduler(Protocol):
    def __init__(
        self,
        node_name: str,
        host: Host,
        qnos: Qnos,
        netstack: Netstack,
        memmgr: MemoryManager,
        local_env: LocalEnvironment,
    ) -> None:
        super().__init__(name=f"{node_name}_scheduler")

        self._node_name = node_name

        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({node_name})"
        )

        self._host = host
        self._qnos = qnos
        self._netstack = netstack
        self._memmgr = memmgr
        self._local_env = local_env

        self._prog_instance_counter: int = 0
        self._batch_counter: int = 0
        self._batches: Dict[int, ProgramBatch] = {}  # batch ID -> batch
        self._prog_results: Dict[int, ProgramResult] = {}  # program ID -> result
        self._batch_results: Dict[int, BatchResult] = {}  # batch ID -> result

        self._schedule: Optional[Schedule] = None

    @property
    def host(self) -> Host:
        return self._host

    @property
    def qnos(self) -> Qnos:
        return self._qnos

    @property
    def netstack(self) -> Netstack:
        return self._netstack

    @property
    def memmgr(self) -> MemoryManager:
        return self._memmgr

    def submit_batch(self, batch_info: BatchInfo) -> None:
        prog_instances: List[ProgramInstance] = []

        for i in range(batch_info.num_iterations):
            instance = ProgramInstance(
                pid=self._prog_instance_counter,
                program=batch_info.program,
                inputs=batch_info.inputs[i],
                tasks=batch_info.tasks,
            )
            self._prog_instance_counter += 1
            prog_instances.append(instance)

        batch = ProgramBatch(
            batch_id=self._batch_counter, info=batch_info, instances=prog_instances
        )
        self._batches[batch.batch_id] = batch
        self._batch_counter += 1

    def get_tasks_to_schedule(self) -> SchedulerInput:
        num_programs = len(self._batches)
        deadlines = [b.info.deadline for b in self._batches.values()]
        num_executions = [b.info.num_iterations for b in self._batches.values()]
        tasks: Dict[int, ProgramTaskList]  # batch ID -> task list
        tasks = {i: b.info.tasks for i, b in self._batches.items()}
        num_instructions = [len(task.tasks) for _, task in tasks.items()]
        instr_durations = [
            [t.duration for t in task.tasks.values()] for _, task in tasks.items()
        ]
        instr_types = [
            [t.instr_type for t in task.tasks.values()] for _, task in tasks.items()
        ]

        return SchedulerInput(
            global_schedule=[0, 1],
            timeslot_len=100,
            num_programs=num_programs,
            deadlines=deadlines,
            num_executions=num_executions,
            num_instructions=num_instructions,
            instr_durations=instr_durations,
            instr_types=instr_types,
        )

    def solver_output_to_schedule(self, output: SchedulerOutput) -> Schedule:
        schedule_entries: List[Tuple[ScheduleTime, ScheduleEntry]] = []
        for entry in output.entries:
            batch_id = entry.app_index
            batch = self._batches[batch_id]
            instance_idx = entry.ex_index
            prog_instance = batch.instances[instance_idx]
            pid = prog_instance.pid
            task_index = entry.instr_index
            time = entry.start_time  # note: may be None!
            schedule_entries.append(
                (ScheduleTime(time), ScheduleEntry(pid, task_index))
            )
        return Schedule(schedule_entries)

    def solve_and_install_schedule(self, solver: Type[ScheduleSolver]) -> None:
        solver_input = self.get_tasks_to_schedule()
        solver_output = solver.solve(solver_input)
        schedule = self.solver_output_to_schedule(solver_output)
        self.install_schedule(schedule)

    def create_processes_for_batches(self) -> None:
        for batch in self._batches.values():
            for prog_instance in batch.instances:
                prog_memory = ProgramMemory(
                    prog_instance.pid,
                    unit_module=UnitModule.default_generic(batch.info.num_qubits),
                )
                meta = prog_instance.program.meta

                csockets: Dict[int, ClassicalSocket] = {}
                for i, remote_name in meta.csockets.items():
                    # TODO: check for already existing epr sockets
                    csockets[i] = self.host.create_csocket(remote_name)

                epr_sockets: Dict[int, EprSocket] = {}
                for i, remote_name in meta.epr_sockets.items():
                    global_env = self._local_env.get_global_env()
                    remote_id = global_env.get_node_id(remote_name)
                    # TODO: check for already existing epr sockets
                    # TODO: fidelity
                    epr_sockets[i] = EprSocket(i, remote_id, 1.0)

                result = ProgramResult(values={})

                process = IqoalaProcess(
                    prog_instance=prog_instance,
                    prog_memory=prog_memory,
                    csockets=csockets,
                    epr_sockets=epr_sockets,
                    subroutines=prog_instance.program.subroutines,
                    requests=prog_instance.program.requests,
                    result=result,
                )

                self.memmgr.add_process(process)
                self.initialize_process(process)

    def collect_batch_results(self) -> None:
        for batch_id, batch in self._batches.items():
            results: List[ProgramResult] = []
            for prog_instance in batch.instances:
                process = self.memmgr.get_process(prog_instance.pid)
                results.append(process.result)
            self._batch_results[batch_id] = BatchResult(batch_id, results)

    def get_batch_results(self) -> Dict[int, BatchResult]:
        return self._batch_results

    def execute_host_task(
        self, process: IqoalaProcess, task: HostTask
    ) -> Generator[EventExpression, None, None]:
        yield from self.host.processor.assign(process, task.instr_index)

    def execute_qnos_task(
        self, process: IqoalaProcess, task: QnosTask
    ) -> Generator[EventExpression, None, None]:
        yield from self.qnos.processor.assign(
            process, task.subrt_name, task.instr_index
        )
        # TODO: improve this
        subrt = process.subroutines[task.subrt_name]
        if task.instr_index == (len(subrt.subroutine.instructions) - 1):
            # subroutine finished -> return results to host
            self.host.processor.copy_subroutine_results(process, task.subrt_name)

    def run_epr_subroutine(
        self, process: IqoalaProcess, subrt_name: str
    ) -> Generator[EventExpression, None, None]:
        subrt = process.subroutines[subrt_name]
        epr_instr_idx = None
        for i, instr in enumerate(subrt.subroutine.instructions):
            if isinstance(instr, CreateEPRInstruction) or isinstance(
                instr, RecvEPRInstruction
            ):
                epr_instr_idx = i
                break

        # Set up arrays
        for i in range(epr_instr_idx):
            yield from self.qnos.processor.assign(process, subrt_name, i)

        request_name = subrt.request_name
        assert request_name is not None
        request = process.requests[request_name].request

        # Handle request
        yield from self.netstack.processor.assign(process, request)

        # Execute wait instruction
        yield from self.qnos.processor.assign(process, subrt_name, epr_instr_idx + 1)

        # Return subroutine results
        self.host.processor.copy_subroutine_results(process, subrt_name)

    def execute_netstack_task(
        self, process: IqoalaProcess, task: NetstackTask
    ) -> Generator[EventExpression, None, None]:
        yield from self.run_epr_subroutine(process, task.subrt_name)

    def execute_task(
        self, process: IqoalaProcess, task: ProgramTask
    ) -> Generator[EventExpression, None, None]:
        if task.processor_type == ProcessorType.HOST:
            yield from self.execute_host_task(process, task.as_host_task())
        elif task.processor_type == ProcessorType.QNOS:
            yield from self.execute_qnos_task(process, task.as_qnos_task())
        elif task.processor_type == ProcessorType.NETSTACK:
            yield from self.execute_netstack_task(process, task.as_netstack_task())
        else:
            raise RuntimeError

    def initialize_process(self, process: IqoalaProcess) -> None:
        # Write program inputs to host memory.
        self.host.processor.initialize(process)

        inputs = process.prog_instance.inputs
        for req in process.requests.values():
            # TODO: support for other request parameters being templates?
            remote_id = req.request.remote_id
            if isinstance(remote_id, Template):
                req.request.remote_id = inputs.values[remote_id.name]

    def install_schedule(self, schedule: Schedule) -> None:
        self._schedule = schedule

    def wait(self, delta_time: int) -> Generator[EventExpression, None, None]:
        self._schedule_after(delta_time, EVENT_WAIT)
        event_expr = EventExpression(source=self, event_type=EVENT_WAIT)
        yield event_expr

    def run(self) -> Generator[EventExpression, None, None]:
        if self._schedule is None:
            return

        for schedule_time, entry in self._schedule.entries:
            process = self.memmgr.get_process(entry.pid)
            task_list = process.prog_instance.tasks
            task = task_list.tasks[entry.task_index]

            if schedule_time.time is None:  # no time constraint
                yield from self.execute_task(process, task)
            else:
                ns_time = ns.sim_time()
                delta = schedule_time.time - ns.sim_time()
                print(
                    f"{self.name} next scheduled time = {schedule_time.time}, delta = {delta}"
                )
                yield from self.wait(delta)
                print(f"{self.name} ns_time: {ns_time}, executing task {task}")
                yield from self.execute_task(process, task)
                print(f"{self.name} s_time: {ns_time}, finished task {task}")

        print(f"{self.name} finished with schedule\n\n")
        self.collect_batch_results()
