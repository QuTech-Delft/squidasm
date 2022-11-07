from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Generator, List, Optional, Set
from xml.dom import NOT_SUPPORTED_ERR

import numpy as np
from netsquid.components.instructions import INSTR_INIT, Instruction
from netsquid.components.qprocessor import MissingInstructionError, QuantumProcessor
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node
from netsquid.qubits import qubitapi
from netsquid.qubits.qubit import Qubit

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


class UnsupportedQDeviceCommandError(Exception):
    pass


class NonInitializedQubitError(Exception):
    pass


@dataclass(eq=True, frozen=True)
class QDeviceCommand:
    instr: Instruction
    indices: List[int]
    angle: Optional[float] = None


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

    def is_allowed(self, cmd: QDeviceCommand) -> bool:
        all_phys_instructions = self.qprocessor.get_physical_instructions()

        # Get the physical instruction with the same type ('gate').
        matches = [
            i for i in all_phys_instructions if i.instruction.name == cmd.instr.name
        ]
        # Should be at least one matching.
        if len(matches) == 0:
            return False

        for phys_instr in matches:
            # If there is no topology, this instruction is allowed on any qubit.
            if phys_instr.topology is None:
                return True

            # Else, check if it is allowed for our current qubit(s).
            if len(cmd.indices) == 1:
                if cmd.indices[0] in phys_instr.topology:
                    return True
            else:
                if cmd.indices in phys_instr.topology:
                    return True

        # We didn't find any matching instruction.
        return False

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        self.qprocessor.mem_positions[id].in_use = in_use

    def execute_commands(
        self, commands: List[QDeviceCommand]
    ) -> Generator[EventExpression, None, Optional[int]]:
        """Can only return at most 1 measurement result."""
        prog = QuantumProgram()

        # TODO: rewrite this abomination

        for cmd in commands:
            # Check if this instruction is allowed on this processor.
            # If not, NetSquid will just silently skip this instruction which is confusing.
            if not self.is_allowed(cmd):
                raise UnsupportedQDeviceCommandError

        for cmd in commands:
            # Check if the qubit has been initialized, since instructions won't work
            # if this is not the case.
            # Anything after an INSTR_INIT instruction is fine.
            # TODO: better logic for detecting INITs of individual qubits.
            if cmd.instr == INSTR_INIT:
                break
            for index in cmd.indices:
                if self.get_local_qubit(index) is None:
                    raise NonInitializedQubitError

        for cmd in commands:
            if cmd.angle is not None:
                prog.apply(cmd.instr, qubit_indices=cmd.indices, angle=cmd.angle)
            else:
                prog.apply(cmd.instr, qubit_indices=cmd.indices)
        yield self.qprocessor.execute_program(prog)

        last_result = prog.output["last"]
        if last_result is not None:
            meas_outcome: int = last_result[0]
            return meas_outcome
        return

    def execute_program(
        self, prog: QuantumProgram
    ) -> Generator[EventExpression, None, None]:
        raise DeprecationWarning

    def get_local_qubit(self, index: int) -> Qubit:
        return self.qprocessor.peek([index], skip_noise=True)[0]

    def get_local_qubits(self, indices: List[int]) -> List[Qubit]:
        return self.qprocessor.peek(indices, skip_noise=True)
