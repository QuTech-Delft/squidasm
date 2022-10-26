import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from squidasm.qoala.sim.hostprocessor import IqoalaProcess
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import (
    CommQubitTrait,
    ProgramMemory,
    QuantumMemory,
    UnitModule,
)
from squidasm.qoala.sim.qdevice import AllocError, QDevice


@dataclass
class VirtualMapping:
    # mapping from virt ID in specific unit module to phys ID
    unit_module: UnitModule
    mapping: Dict[int, Optional[int]]  # virt ID -> phys ID


@dataclass
class VirtualLocation:
    # particular virt ID in particular unit module in particular process
    pid: int
    unit_module: UnitModule
    virt_id: int


class MemoryManager:
    def __init__(self, node_name: str, qdevice: QDevice) -> None:
        self._node_name = node_name
        self._processes: Dict[int, IqoalaProcess] = {}
        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({self._node_name})"
        )

        self._qdevice = qdevice
        self._process_mappings: Dict[int, VirtualMapping] = {}  # pid -> mapping
        self._physical_mapping: Dict[
            int, Optional[VirtualLocation]
        ] = {}  # phys ID -> virt location

    def add_process(self, process: IqoalaProcess) -> None:
        self._processes[process.pid] = process
        unit_module = process.prog_memory.quantum_mem.unit_module
        self._process_mappings[process.pid] = VirtualMapping(
            unit_module, {x: None for x in unit_module.qubit_ids}
        )

    def _virt_qubit_is_comm(self, unit_module: UnitModule, virt_id: int) -> bool:
        traits = unit_module.qubit_traits[virt_id]
        return any(isinstance(t, CommQubitTrait) for t in traits)

    def allocate(self, pid: int, virt_id: int) -> int:
        vmap = self._process_mappings[pid]
        # Check if the virtual ID is in the unit module
        assert virt_id in vmap.unit_module.qubit_ids

        phys_id: int
        if self._virt_qubit_is_comm(vmap.unit_module, virt_id):
            phys_id = self._get_free_comm_phys_id()
        else:
            phys_id = self._get_free_mem_phys_id()

        # update mappings
        self._physical_mapping[phys_id] = VirtualLocation(
            pid, vmap.unit_module, virt_id
        )
        self._process_mappings[pid].mapping[virt_id] = phys_id
        return phys_id

    def _get_free_comm_phys_id(self) -> int:
        for phys_id in self._qdevice.memory.comm_qubit_ids:
            if self._physical_mapping[phys_id] is None:
                return phys_id
        raise AllocError

    def _get_free_mem_phys_id(self) -> int:
        for phys_id in self._qdevice.memory.mem_qubit_ids:
            if self._physical_mapping[phys_id] is None:
                return phys_id
        raise AllocError

    def _get_quantum_memories(self) -> Dict[int, QuantumMemory]:
        return {
            pid: proc.prog_memory.quantum_mem for (pid, proc) in self._processes.items()
        }

    def get_program_memory(self, pid: int) -> ProgramMemory:
        return self._processes[pid].prog_memory

    def get_quantum_memory(self, pid: int) -> QuantumMemory:
        return self.get_program_memory(pid).quantum_mem

    def _phys_to_virt_id(self, phys_id: int) -> Tuple[int, int]:
        # returns (pid, virt_id)
        quantum_memories = self._get_quantum_memories()
        for pid, mem in quantum_memories.items():
            virt_id = mem.virt_id_for(phys_id)
            if virt_id is not None:
                return pid, virt_id
        raise RuntimeError(f"no virtual ID found for physical ID {phys_id}")

    def move_phys_qubit(self, phys_id: int, new_phys_id: int) -> None:
        pid, virt_id = self._phys_to_virt_id(phys_id)
        self._logger.warning(
            f"moving virtual qubit {virt_id} from process "
            f"{pid} from physical ID {phys_id} to {new_phys_id}"
        )
        quantum_memories = self._get_quantum_memories()
        quantum_memories[pid].unmap_virt_id(virt_id)
        quantum_memories[pid].map_virt_id(virt_id, new_phys_id)

    def map_virt_id(self, pid: int, virt_id: int, phys_id: int) -> None:
        mem = self.get_quantum_memory(pid)
        mem.map_virt_id(virt_id, phys_id)

    def unmap_virt_id(self, pid: int, virt_id: int) -> None:
        mem = self.get_quantum_memory(pid)
        mem.unmap_virt_id(virt_id)

    def get_mapping(self, pid: int) -> Dict[int, Optional[int]]:
        mem = self.get_quantum_memory(pid)
        return mem.qubit_mapping

    def phys_id_for(self, pid: int, virt_id: int) -> int:
        mem = self.get_quantum_memory(pid)
        return mem.phys_id_for(virt_id)

    def virt_id_for(self, pid: int, phys_id: int) -> Optional[int]:
        mem = self.get_quantum_memory(pid)
        return mem.virt_id_for(phys_id)
