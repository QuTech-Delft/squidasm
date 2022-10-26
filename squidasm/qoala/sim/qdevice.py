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
        self._mem_qubit_ids: Set[int] = {i for i in range(qubit_count)}

    @property
    def qubit_count(self) -> int:
        return self._qubit_count

    @property
    def comm_qubit_count(self) -> int:
        return len(self._comm_qubit_ids)

    @property
    def comm_qubit_ids(self) -> Set[int]:
        return self._comm_qubit_ids

    @property
    def mem_qubit_ids(self) -> Set[int]:
        return self._mem_qubit_ids


class NVPhysicalQuantumMemory(PhysicalQuantumMemory):
    def __init__(self, qubit_count: int) -> None:
        super().__init__(qubit_count)
        self._comm_qubit_ids: Set[int] = {0}
        self._mem_qubit_ids: Set[int] = {i for i in range(1, qubit_count)}


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

    @property
    def qubit_count(self) -> int:
        return self.memory.qubit_count

    @property
    def comm_qubit_count(self) -> int:
        return self.memory.comm_qubit_count

    @property
    def comm_qubit_ids(self) -> Set[int]:
        return self.memory.comm_qubit_ids

    @property
    def mem_qubit_ids(self) -> Set[int]:
        return self.memory.mem_qubit_ids

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        self.qprocessor.mem_positions[id].in_use = in_use

    def execute_program(
        self, prog: QuantumProgram
    ) -> Generator[EventExpression, None, None]:
        yield self.qprocessor.execute_program(prog)
