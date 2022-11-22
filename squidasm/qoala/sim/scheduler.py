from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional

import netsquid as ns
from netqasm.lang.instr.core import CreateEPRInstruction, RecvEPRInstruction
from netqasm.lang.operand import Template
from netsquid.components.component import Component
from netsquid.nodes import Node
from netsquid.protocols import Protocol

from pydynaa import EventExpression, EventType
from squidasm.qoala.lang import iqoala
from squidasm.qoala.runtime.program import BatchResult, ProgramInstance
from squidasm.qoala.runtime.schedule import (
    HostTask,
    NetstackTask,
    ProcessorType,
    ProgramTask,
    QnosTask,
    Schedule,
)
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.netstack import Netstack
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qnos import Qnos

EVENT_WAIT = EventType("SCHEDULER_WAIT", "scheduler wait")


class Scheduler(Protocol):
    def __init__(
        self,
        node_name: str,
        host: Host,
        qnos: Qnos,
        netstack: Netstack,
        memmgr: MemoryManager,
    ) -> None:
        super().__init__(name=f"{node_name}_scheduler")

        self._node_name = node_name

        self._host = host
        self._qnos = qnos
        self._netstack = netstack
        self._memmgr = memmgr

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
        yield from self.wait(task.duration)

    def initialize(self, process: IqoalaProcess) -> None:
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
                yield from self.wait(delta)
                print(f"ns_time: {ns_time}, executing task {task}")
                yield from self.execute_task(process, task)
                print(f"ns_time: {ns_time}, finished task {task}")
