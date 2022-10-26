from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import netsquid as ns
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import (
    IqoalaProgram,
    IqoalaSharedMemLoc,
    IqoalaSubroutine,
    ProgramMeta,
)
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.util.tests import yield_from


def create_process(unit_module: UnitModule) -> IqoalaProcess:
    program = IqoalaProgram(
        instructions=[], subroutines={}, meta=ProgramMeta.empty("prog")
    )
    instance = ProgramInstance(pid=0, program=program, inputs=ProgramInput({}))
    mem = ProgramMemory(pid=0, unit_module=unit_module)

    process = IqoalaProcess(
        prog_instance=instance,
        prog_memory=mem,
        csockets={},
        epr_sockets=program.meta.epr_sockets,
        subroutines=program.subroutines,
        result=ProgramResult(values={}),
    )
    return process


def test_1():
    mgr = MemoryManager("alice")
    process = create_process(UnitModule.default_generic(num_qubits=2))
    mgr.add_process(process)

    assert mgr.get_program_memory(process.pid) == process.prog_memory
    assert mgr.get_quantum_memory(process.pid) == process.prog_memory.quantum_mem

    assert mgr.get_mapping(process.pid) == {0: None, 1: None}


if __name__ == "__main__":
    test_1()
