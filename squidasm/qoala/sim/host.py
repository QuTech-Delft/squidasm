from __future__ import annotations

from typing import Dict, Generator

import netsquid as ns
from netsquid.protocols import Protocol

from pydynaa import EventExpression, EventType
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.common import ComponentProtocol
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.hostprocessor import HostProcessor, IqoalaProcess
from squidasm.qoala.sim.scheduler import Scheduler

EVENT_WAIT = EventType("SCHEDULER_WAIT", "scheduler wait")


class Host(Protocol):
    """NetSquid protocol representing a Host."""

    def __init__(
        self,
        comp: HostComponent,
        local_env: LocalEnvironment,
        scheduler: Scheduler,
        asynchronous: bool = False,
    ) -> None:
        """Host protocol constructor.

        :param comp: NetSquid component representing the Host
        """
        super().__init__(name=f"{comp.name}_protocol")

        # References to objects.
        self._comp = comp
        self._scheduler = scheduler
        self._local_env = local_env

        # Owned objects.
        self._interface = HostInterface(comp, local_env)
        self._processor = HostProcessor(self._interface, asynchronous)
        self._processes: Dict[int, IqoalaProcess] = {}

    @property
    def interface(self) -> HostInterface:
        return self._interface

    @interface.setter
    def interface(self, interface: HostInterface) -> None:
        self._interface = interface
        self._processor._interface = interface

    @property
    def processor(self) -> HostProcessor:
        return self._processor

    @property
    def local_env(self) -> LocalEnvironment:
        return self._local_env

    def run(self) -> Generator[EventExpression, None, None]:
        pass
        # while True:
        #     task = self._scheduler.next_host_task()
        #     if task.no_more_tasks:
        #         break

        #     process = self._processes[task.pid]
        #     yield from self.processor.assign(process, task.instr_idx)

    def start(self) -> None:
        assert self._interface is not None
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()

    def create_csocket(self, remote_name: str) -> ClassicalSocket:
        return ClassicalSocket(self._interface, remote_name)

    def add_process(self, process: IqoalaProcess) -> None:
        self._processes[process.prog_instance.pid] = process

    def wait_until_next_slot(self) -> Generator[EventExpression, None, None]:
        now = ns.sim_time()
        next_slot = self._local_schedule.next_slot(now)
        delta = next_slot - now
        self._logger.warning(f"next slot = {next_slot}")
        self._logger.warning(f"delta = {delta}")
        self._schedule_after(delta, EVENT_WAIT)
        event_expr = EventExpression(source=self, event_type=EVENT_WAIT)
        yield event_expr
