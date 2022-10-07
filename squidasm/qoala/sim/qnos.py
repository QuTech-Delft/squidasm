from __future__ import annotations

from typing import Dict, Tuple

from netsquid.protocols import Protocol

from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice, QDeviceType
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import (
    GenericProcessor,
    NVProcessor,
    QnosProcessor,
)
from squidasm.qoala.sim.scheduler import Scheduler


class Qnos(Protocol):
    """NetSquid protocol representing a QNodeOS instance."""

    def __init__(
        self,
        comp: QnosComponent,
        local_env: LocalEnvironment,
        scheduler: Scheduler,
        qdevice: QDevice,
    ) -> None:
        """Qnos protocol constructor.

        :param comp: NetSquid component representing the QNodeOS instance
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol")

        # References to objects.
        self._comp = comp
        self._scheduler = scheduler
        self._local_env = local_env

        # Owned objects.
        self._interface = QnosInterface(comp, qdevice)
        self._processor: QnosProcessor
        self._processes: Dict[int, IqoalaProcess] = {}  # program ID -> process
        # TODO: make self._processes fully referenced object?

        if qdevice.typ == QDeviceType.GENERIC:
            self._processor = GenericProcessor()
        elif qdevice.typ == QDeviceType.NV:
            self._processor = NVProcessor()
        else:
            raise ValueError

    # TODO: move this to a separate memory manager object
    def get_virt_qubit_for_phys_id(self, phys_id: int) -> Tuple[int, int]:
        # returns (pid, virt_id)
        for pid, mem in self.quantum_memories:
            virt_id = mem.virt_id_for(phys_id)
            if virt_id is not None:
                return pid, virt_id
        raise RuntimeError(f"no virtual ID found for physical ID {phys_id}")

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
