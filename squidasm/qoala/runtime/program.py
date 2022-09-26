import abc
from dataclasses import dataclass
from typing import Any, Dict, List

from squidasm.qoala.lang.iqoala import IqoalaProgram


class ProgramContext(abc.ABC):
    pass


@dataclass
class BatchInfo:
    """Description of a batch of program instances that should be executed."""

    program: IqoalaProgram
    inputs: List[Dict[str, Any]]  # dict of inputs for each iteration
    num_iterations: int
    deadline: float


@dataclass
class ProgramInstance:
    """A running program"""

    pid: int
    program: IqoalaProgram
    inputs: Dict[str, Any]


@dataclass
class ProgramBatch:
    info: BatchInfo
    instances: List[ProgramInstance]


@dataclass
class BatchResult:
    results: List[Dict[str, Any]]
