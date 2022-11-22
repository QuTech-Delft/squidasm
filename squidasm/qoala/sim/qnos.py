from __future__ import annotations

from typing import Dict

from netsquid.protocols import Protocol

from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice, QDeviceType
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import (
    GenericProcessor,
    NVProcessor,
    QnosProcessor,
)


class Qnos(Protocol):
    """NetSquid protocol representing a QNodeOS instance."""

    def __init__(
        self,
        comp: QnosComponent,
        local_env: LocalEnvironment,
        memmgr: MemoryManager,
        qdevice: QDevice,
        asynchronous: bool = False,
    ) -> None:
        """Qnos protocol constructor.

        :param comp: NetSquid component representing the QNodeOS instance
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol")

        # References to objects.
        self._comp = comp
        self._local_env = local_env

        # Owned objects.
        self._interface = QnosInterface(comp, qdevice, memmgr)
        self._processor: QnosProcessor
        self._asynchronous = asynchronous

        self.create_processor(qdevice.typ)

    def create_processor(self, qdevice_type: QDeviceType) -> None:
        if qdevice_type == QDeviceType.GENERIC:
            self._processor = GenericProcessor(self._interface, self._asynchronous)
        elif qdevice_type == QDeviceType.NV:
            self._processor = NVProcessor(self._interface, self._asynchronous)
        else:
            raise ValueError

    @property
    def qdevice(self) -> QDevice:
        return self._interface.qdevice

    @qdevice.setter
    def qdevice(self, qdevice: QDevice) -> None:
        self._interface._qdevice = qdevice
        self.create_processor(qdevice.typ)

    @property
    def processor(self) -> QnosProcessor:
        return self._processor

    @processor.setter
    def processor(self, processor: QnosProcessor) -> None:
        self._processor = processor

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        return self._interface.qdevice.memory

    def start(self) -> None:
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()
