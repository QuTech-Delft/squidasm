from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import StopAppMessage

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.runtime.program import BatchResult
from squidasm.qoala.sim.common import ComponentProtocol
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.hostprocessor import HostProcessor, IqoalaProcess
from squidasm.qoala.sim.scheduler import Scheduler


class Host(ComponentProtocol):
    """NetSquid protocol representing a Host."""

    def __init__(
        self,
        comp: HostComponent,
        local_env: LocalEnvironment,
        scheduler: Scheduler,
        qdevice_type: Optional[str] = "nv",
    ) -> None:
        """Host protocol constructor.

        :param comp: NetSquid component representing the Host
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._interface = HostInterface(comp, local_env)

        self._processor = HostProcessor(self)
        self._processes: Dict[int, IqoalaProcess] = {}

        self._scheduler = scheduler

    @property
    def processor(self) -> HostProcessor:
        return self._processor

    @property
    def local_env(self) -> LocalEnvironment:
        return self._local_env

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            task = self._scheduler.next_host_task()
            if task.no_more_tasks:
                break

            process = self._processes[task.pid]
            yield from self.processor.assign(process, task.instr_idx)

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
