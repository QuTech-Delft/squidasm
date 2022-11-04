from dataclasses import dataclass
from typing import Dict

from squidasm.qoala.lang.iqoala import IqoalaSubroutine
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
    subroutines: Dict[str, IqoalaSubroutine]
    result: ProgramResult

    @property
    def pid(self) -> int:
        return self.prog_instance.pid