from __future__ import annotations

from typing import Dict, Generator

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.common import ComponentProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice
from squidasm.qoala.sim.scheduler import Scheduler


class Netstack(ComponentProtocol):
    """NetSquid protocol representing the QNodeOS network stack."""

    def __init__(
        self,
        comp: NetstackComponent,
        local_env: LocalEnvironment,
        memmgr: MemoryManager,
        egpmgr: EgpManager,
        scheduler: Scheduler,
        qdevice: QDevice,
    ) -> None:
        """Network stack protocol constructor. Typically created indirectly through
        constructing a `Qnos` instance.

        :param comp: NetSquid component representing the network stack
        :param qnos: `Qnos` protocol that owns this protocol
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)

        # References to objects.
        self._comp = comp
        self._scheduler = scheduler
        self._local_env = local_env

        # Values are references to objects created elsewhere
        self._processes: Dict[int, IqoalaProcess] = {}  # program ID -> process

        # Owned objects.
        self._interface = NetstackInterface(comp, local_env, qdevice, memmgr, egpmgr)
        self._processor = NetstackProcessor(self._interface)

    def run(self) -> Generator[EventExpression, None, None]:
        # Loop forever acting on messages from the processor.
        while True:
            # Wait for a new message.
            msg = yield from self._interface.receive_qnos_msg()
            self._logger.debug(f"received new msg from processor: {msg}")
            request = msg.content

    def add_process(self, process: IqoalaProcess) -> None:
        self._processes[process.prog_instance.pid] = process

    def start(self) -> None:
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()
