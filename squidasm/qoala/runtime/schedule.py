from dataclasses import dataclass
from enum import Enum, auto
from optparse import Option
from typing import Dict, Optional, Union

# CL: host 0
# CL: host 1
# QC: netstack "create_epr_0"
# CL: host 2
# QC: netstack "create_epr_1"
# CL: host 3
# QL: qnos "local_cphase" 0
# QL: qnos "local_cphase" 1
# QL: qnos "local_cphase" 2
# CC: host 4
# CL: host 5
# QL: qnos "meas_qubit_1" 0
# QL: qnos "meas_qubit_1" 1
# QL: qnos "meas_qubit_1" 2
# QL: qnos "meas_qubit_1" 3
# QL: qnos "meas_qubit_1" 4
# QL: qnos "meas_qubit_1" 5
# CC: host 6
# CC: host 7
# CL: host 8
# QL: qnos "meas_qubit_0" 0
# QL: qnos "meas_qubit_0" 1
# QL: qnos "meas_qubit_0" 2
# QL: qnos "meas_qubit_0" 3
# QL: qnos "meas_qubit_0" 4
# QL: qnos "meas_qubit_0" 5
# CL: host 9
# CL: host 10


class ProcessorType(Enum):
    HOST = 0
    QNOS = auto()
    NETSTACK = auto()


class InstructionType(Enum):
    CL = 0
    CC = auto()
    QL = auto()
    QC = auto()


@dataclass
class HostTask:
    instr_index: int


@dataclass
class QnosTask:
    subrt_name: str
    instr_index: int


@dataclass
class NetstackTask:
    request_name: str


@dataclass
class ProgramTask:
    instr_type: InstructionType
    processor_type: ProcessorType
    instr_index: Optional[int]
    subrt_name: Optional[str]
    request_name: Optional[str]

    def as_host_task(self) -> HostTask:
        assert self.processor_type == ProcessorType.HOST
        assert self.instr_index is not None
        return HostTask(self.instr_index)

    def as_qnos_task(self) -> QnosTask:
        assert self.processor_type == ProcessorType.QNOS
        assert self.subrt_name is not None
        return QnosTask(self.subrt_name, self.instr_index)

    def as_netstack_task(self) -> NetstackTask:
        assert self.processor_type == ProcessorType.NETSTACK
        assert self.request_name is not None
        return NetstackTask(self.request_name)


class TaskBuilder:
    @classmethod
    def host_task(cls, index: int) -> ProgramTask:
        return ProgramTask(
            instr_type=ProcessorType.HOST,
            instr_index=index,
            subrt_name=None,
            request_name=None,
        )

    @classmethod
    def qnos_task(cls, subrt_name: str, index: int) -> ProgramTask:
        return ProgramTask(
            instr_type=ProcessorType.QNOS,
            instr_index=index,
            subrt_name=subrt_name,
            request_name=None,
        )

    @classmethod
    def netstack_task(cls, request_name: str) -> ProgramTask:
        return ProgramTask(
            instr_type=ProcessorType.NETSTACK,
            instr_index=None,
            subrt_name=None,
            request_name=request_name,
        )


class Schedule:
    def __init__(self, timeslot_length: int) -> None:
        self._program = Dict[int, ProgramTask] = {}  # task index -> task
        self._schedule: Dict[int, int] = {}  # task index -> time

        self._timeslot_length = timeslot_length

    def next_slot(self, now: float) -> int:
        slot = int(now / self._timeslot_length)
        return (slot + 1) * self._timeslot_length
