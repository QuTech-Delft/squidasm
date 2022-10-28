from enum import Enum, auto
from typing import Generator, Set

from netsquid.components import QuantumProcessor
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node

from pydynaa import EventExpression


class QDeviceType(Enum):
    GENERIC = 0
    NV = auto()


class PhysicalQuantumMemory:
    def __init__(self, comm_ids: Set[int], mem_ids: Set[int]) -> None:
        self._comm_qubit_ids: Set[int] = comm_ids
        self._mem_qubit_ids: Set[int] = mem_ids
        self._all_ids = comm_ids.union(mem_ids)
        self._qubit_count = len(self._all_ids)

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


class GenericPhysicalQuantumMemory(PhysicalQuantumMemory):
    def __init__(self, qubit_count: int) -> None:
        super().__init__(
            comm_ids={i for i in range(qubit_count)},
            mem_ids={i for i in range(qubit_count)},
        )


class NVPhysicalQuantumMemory(PhysicalQuantumMemory):
    def __init__(self, qubit_count: int) -> None:
        super().__init__(comm_ids={0}, mem_ids={i for i in range(1, qubit_count)})


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

    @property
    def all_qubit_ids(self) -> Set[int]:
        return self.comm_qubit_ids.union(self.mem_qubit_ids)

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        self.qprocessor.mem_positions[id].in_use = in_use

    def execute_program(
        self, prog: QuantumProgram
    ) -> Generator[EventExpression, None, None]:
        yield self.qprocessor.execute_program(prog)
