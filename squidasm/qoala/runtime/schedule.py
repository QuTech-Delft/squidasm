from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from squidasm.qoala.lang.iqoala import IqoalaProgram


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
    # request_name: str  # TODO: needed?
    subrt_name: str


@dataclass
class ProgramTask:
    instr_type: InstructionType
    processor_type: ProcessorType
    instr_index: Optional[int]
    subrt_name: Optional[str]
    request_name: Optional[str]
    duration: int

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
        assert self.subrt_name is not None
        return NetstackTask(self.subrt_name)


class TaskBuilder:
    @classmethod
    def CC(cls, duration, index: int) -> ProgramTask:
        return ProgramTask(
            instr_type=InstructionType.CC,
            processor_type=ProcessorType.HOST,
            instr_index=index,
            subrt_name=None,
            request_name=None,
            duration=duration,
        )

    @classmethod
    def CL(cls, duration, index: int) -> ProgramTask:
        return ProgramTask(
            instr_type=InstructionType.CL,
            processor_type=ProcessorType.HOST,
            instr_index=index,
            subrt_name=None,
            request_name=None,
            duration=duration,
        )

    @classmethod
    def QL(cls, duration, subrt_name: str, index: int) -> ProgramTask:
        return ProgramTask(
            instr_type=InstructionType.QL,
            processor_type=ProcessorType.QNOS,
            instr_index=index,
            subrt_name=subrt_name,
            request_name=None,
            duration=duration,
        )

    @classmethod
    def QC(cls, duration, subrt_name: str) -> ProgramTask:
        return ProgramTask(
            instr_type=InstructionType.QC,
            processor_type=ProcessorType.NETSTACK,
            instr_index=None,
            subrt_name=subrt_name,
            request_name=None,
            duration=duration,
        )


@dataclass
class ProgramTaskList:
    program: IqoalaProgram
    tasks: Dict[int, ProgramTask]  # task index -> task

    @classmethod
    def empty(cls, program: IqoalaProgram) -> ProgramTaskList:
        return ProgramTaskList(program, {})


@dataclass(eq=True, frozen=True)
class ScheduleEntry:
    pid: int
    task_index: int


@dataclass(eq=True, frozen=True)
class ScheduleTime:
    time: Optional[int]  # None means "earliest time possible"


@dataclass
class Schedule:
    entries: List[Tuple[ScheduleTime, ScheduleEntry]]  # list of (time, entry)
