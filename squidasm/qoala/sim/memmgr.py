import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from squidasm.qoala.sim.hostprocessor import IqoalaProcess
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import CommQubitTrait, MemQubitTrait, UnitModule
from squidasm.qoala.sim.qdevice import QDevice


class AllocError(Exception):
    pass


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
        self._physical_mapping: Dict[int, Optional[VirtualLocation]] = {
            i: None for i in qdevice.all_qubit_ids
        }  # phys ID -> virt location

    def _virt_qubit_is_comm(self, unit_module: UnitModule, virt_id: int) -> bool:
        traits = unit_module.qubit_traits[virt_id]
        return CommQubitTrait in traits

    def _virt_qubit_is_mem(self, unit_module: UnitModule, virt_id: int) -> bool:
        traits = unit_module.qubit_traits[virt_id]
        return MemQubitTrait in traits

    def _get_free_comm_phys_id(self) -> int:
        for phys_id in self._qdevice.comm_qubit_ids:
            if self._physical_mapping[phys_id] is None:
                return phys_id
        raise AllocError

    def _get_free_mem_phys_id(self) -> int:
        for phys_id in self._qdevice.mem_qubit_ids:
            if self._physical_mapping[phys_id] is None:
                return phys_id
        raise AllocError

    def add_process(self, process: IqoalaProcess) -> None:
        self._processes[process.pid] = process
        unit_module = process.prog_memory.quantum_mem.unit_module
        self._process_mappings[process.pid] = VirtualMapping(
            unit_module, {x: None for x in unit_module.qubit_ids}
        )

    def allocate(self, pid: int, virt_id: int) -> int:
        vmap = self._process_mappings[pid]
        # Check if the virtual ID is in the unit module
        if virt_id not in vmap.unit_module.qubit_ids:
            raise AllocError

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

    def free(self, pid: int, virt_id: int) -> None:
        vmap = self._process_mappings[pid]
        # Check if the virtual ID is in the unit module
        assert virt_id in vmap.unit_module.qubit_ids
        assert virt_id in self._process_mappings[pid].mapping

        phys_id = self._process_mappings[pid].mapping[virt_id]
        if phys_id is None:
            raise AllocError

        # update mappings
        self._physical_mapping[phys_id] = None
        self._process_mappings[pid].mapping[virt_id] = None

        # update netsquid memory
        self._qdevice.set_mem_pos_in_use(phys_id, False)

    def get_unmapped_mem_qubit(self, pid: int) -> int:
        """returns virt ID"""
        vp_map = self._process_mappings[pid].mapping
        unit_module = self._process_mappings[pid].unit_module
        free_ids = [
            v
            for v, p in vp_map.items()
            if p is None and self._virt_qubit_is_mem(unit_module, v)
        ]
        if len(free_ids) == 0:
            raise AllocError
        return min(free_ids)

    def phys_id_for(self, pid: int, virt_id: int) -> Optional[int]:
        phys_id = self._process_mappings[pid].mapping[virt_id]
        return phys_id

    def virt_id_for(self, pid: int, phys_id: int) -> Optional[int]:
        if virt_loc := self._physical_mapping[phys_id]:
            if virt_loc.pid == pid:
                return virt_loc.virt_id
        return None
