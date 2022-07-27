import abc
from dataclasses import dataclass
from typing import Any, Dict, Union

from squidasm.qoala.lang.lhr import LhrProgram


class ProgramContext(abc.ABC):
    pass


class SdkProgram(abc.ABC):
    @abc.abstractmethod
    def compile(self, context: ProgramContext) -> LhrProgram:
        raise NotImplementedError


@dataclass
class ProgramInstance:
    program: Union[LhrProgram, SdkProgram]
    inputs: Dict[str, Any]
    num_iterations: int
    deadline: float
