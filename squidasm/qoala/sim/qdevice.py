from enum import Enum, auto
from typing import Generator, Set

from netsquid.components import QuantumProcessor
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node

from pydynaa import EventExpression


class QDeviceType(Enum):
    GENERIC = 0
    NV = auto()


class AllocError(Exception):
    pass


class PhysicalQuantumMemory:
    def __init__(self, qubit_count: int) -> None:
        self._qubit_count = qubit_count
        self._allocated_ids: Set[int] = set()
        self._comm_qubit_ids: Set[int] = {i for i in range(qubit_count)}

    @property
    def qubit_count(self) -> int:
        return self._qubit_count

    @property
    def comm_qubit_count(self) -> int:
        return len(self._comm_qubit_ids)

    def allocate(self) -> int:
        """Allocate a qubit (communcation or memory)."""
        for i in range(self._qubit_count):
            if i not in self._allocated_ids:
                self._allocated_ids.add(i)
                return i
        raise AllocError("No more qubits available")

    def allocate_comm(self) -> int:
        """Allocate a communication qubit."""
        for i in range(self._qubit_count):
            if i not in self._allocated_ids and i in self._comm_qubit_ids:
                self._allocated_ids.add(i)
                return i
        raise AllocError("No more comm qubits available")

    def allocate_mem(self) -> int:
        """Allocate a memory qubit."""
        for i in range(self._qubit_count):
            if i not in self._allocated_ids and i not in self._comm_qubit_ids:
                self._allocated_ids.add(i)
                return i
        raise AllocError("No more mem qubits available")

    def free(self, id: int) -> None:
        self._allocated_ids.remove(id)

    def is_allocated(self, id: int) -> bool:
        return id in self._allocated_ids

    def clear(self) -> None:
        self._allocated_ids = {}


class NVPhysicalQuantumMemory(PhysicalQuantumMemory):
    def __init__(self, qubit_count: int) -> None:
        super().__init__(qubit_count)
        self._comm_qubit_ids: Set[int] = {0}


class QDevice:
    def __init__(
        self, node: Node, typ: QDeviceType, memory: PhysicalQuantumMemory
    ) -> None:
        self._node = node
        self._typ = typ
        self._memory = memory

    @property
    def qprocessor(self) -> QuantumProcessor:
        """Get the NetSquid `QuantumProcessor` object of this node."""
        return self._node.qmemory

    @property
    def typ(self) -> QDeviceType:
        return self._typ

    @property
    def memory(self) -> PhysicalQuantumMemory:
        return self._memory

    def allocate(self) -> int:
        return self._memory.allocate()

    def allocate_comm(self) -> int:
        return self._memory.allocate_comm()

    def allocate_mem(self) -> int:
        return self._memory.allocate_mem()

    def free(self, id: int) -> None:
        self._memory.free(id)

    def is_allocated(self, id: int) -> bool:
        return self._memory.is_allocated(id)

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        self.qprocessor.mem_positions[id].in_use = in_use

    def execute_program(
        self, prog: QuantumProgram
    ) -> Generator[EventExpression, None, None]:
        yield self.qprocessor.execute_program(prog)
