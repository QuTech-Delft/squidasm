from dataclasses import dataclass
from typing import Dict

from netqasm.lang.subroutine import Subroutine

from squidasm.qoala.runtime.program import ProgramInstance, ProgramResult
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.memory import ProgramMemory


@dataclass
class IqoalaProcess:
    prog_instance: ProgramInstance
    prog_memory: ProgramMemory
    csockets: Dict[int, ClassicalSocket]
    epr_sockets: Dict[int, EprSocket]
    subroutines: Dict[str, Subroutine]
    result: ProgramResult
