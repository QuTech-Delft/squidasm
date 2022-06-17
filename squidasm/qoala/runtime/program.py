from dataclasses import dataclass
from typing import Any, Dict

from squidasm.qoala.lang.lhr import LhrProgram


@dataclass
class ProgramInstance:
    program: LhrProgram
    inputs: Dict[str, Any]
    num_iterations: int
    deadline: float
