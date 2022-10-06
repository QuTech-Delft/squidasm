from __future__ import annotations

from typing import Dict, Optional, Tuple

from netqasm.lang.subroutine import Subroutine
from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.common import NVPhysicalQuantumMemory, PhysicalQuantumMemory
from squidasm.qoala.sim.memory import ProgramMemory, QuantumMemory, SharedMemory
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice, QDeviceType
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
        self._comp = comp
        self._interface = QnosInterface(comp)

        self._local_env = local_env

        if qdevice.typ == QDeviceType.GENERIC:
            self.processor = GenericProcessor()
        elif qdevice.typ == QDeviceType.NV:
            self.processor = NVProcessor()
        else:
            raise ValueError

        self._processes: Dict[int, IqoalaProcess] = {}  # program ID -> process
        self._scheduler = scheduler

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
        return self._physical_memory

    def start(self) -> None:
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        """Get the physical quantum memory object."""
        return self._qnos.physical_memory
