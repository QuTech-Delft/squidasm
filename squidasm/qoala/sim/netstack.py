from __future__ import annotations

from typing import Dict, Generator

from netsquid.protocols import Protocol

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice


class Netstack(Protocol):
    """NetSquid protocol representing the QNodeOS network stack."""

    def __init__(
        self,
        comp: NetstackComponent,
        local_env: LocalEnvironment,
        memmgr: MemoryManager,
        egpmgr: EgpManager,
        qdevice: QDevice,
    ) -> None:
        """Network stack protocol constructor. Typically created indirectly through
        constructing a `Qnos` instance.

        :param comp: NetSquid component representing the network stack
        :param qnos: `Qnos` protocol that owns this protocol
        """
        super().__init__(name=f"{comp.name}_protocol")

        # References to objects.
        self._comp = comp
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
            # request = msg.content

    @property
    def qdevice(self) -> QDevice:
        return self._interface.qdevice

    @qdevice.setter
    def qdevice(self, qdevice: QDevice) -> None:
        self._interface._qdevice = qdevice

    @property
    def interface(self) -> NetstackInterface:
        return self._interface

    @interface.setter
    def interface(self, interface: NetstackInterface) -> None:
        self._interface = interface
        self._processor._interface = interface

    @property
    def processor(self) -> NetstackProcessor:
        return self._processor

    @processor.setter
    def processor(self, processor: NetstackProcessor) -> None:
        self._processor = processor

    def add_process(self, process: IqoalaProcess) -> None:
        self._processes[process.prog_instance.pid] = process

    def start(self) -> None:
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()
