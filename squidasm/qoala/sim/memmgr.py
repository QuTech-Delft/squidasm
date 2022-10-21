import logging
from typing import Dict, Tuple

from squidasm.qoala.sim.hostprocessor import IqoalaProcess
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory, QuantumMemory


class MemoryManager:
    def __init__(self, node_name: str) -> None:
        self._node_name = node_name
        self._processes: Dict[int, IqoalaProcess] = {}
        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({self._node_name})"
        )

    def _get_quantum_memories(self) -> Dict[int, QuantumMemory]:
        return {
            pid: mem.prog_memory.quantum_mem for (pid, mem) in self._processes.items()
        }

    def get_program_memory(self, pid: int) -> ProgramMemory:
        return self._processes[pid].prog_memory

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
