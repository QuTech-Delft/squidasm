from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import netsquid as ns
import pytest
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
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import (
    CommQubitTrait,
    MemQubitTrait,
    ProgramMemory,
    SharedMemory,
    UnitModule,
)
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.util.tests import yield_from


class MockQDevice(QDevice):
    def __init__(self) -> None:
        pass

    @property
    def comm_qubit_ids(self) -> Set[int]:
        return {0}

    @property
    def mem_qubit_ids(self) -> Set[int]:
        return {1}

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        pass


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


def setup_manager() -> Tuple[int, MemoryManager]:
    qdevice = MockQDevice()
    mgr = MemoryManager("alice", qdevice)

    um = UnitModule(
        qubit_ids=[0, 1],
        qubit_traits={0: [CommQubitTrait], 1: [MemQubitTrait]},
        gate_traits={},
    )

    process = create_process(um)
    mgr.add_process(process)
    pid = process.pid

    return pid, mgr


def test_alloc_free_0():
    pid, mgr = setup_manager()

    assert mgr.phys_id_for(pid, 0) == None
    assert mgr.phys_id_for(pid, 1) == None
    assert mgr.virt_id_for(pid, 0) == None
    assert mgr.virt_id_for(pid, 1) == None

    mgr.allocate(pid, 0)
    assert mgr.phys_id_for(pid, 0) == 0
    assert mgr.phys_id_for(pid, 1) == None
    assert mgr.virt_id_for(pid, 0) == 0
    assert mgr.virt_id_for(pid, 1) == None

    mgr.free(pid, 0)
    assert mgr.phys_id_for(pid, 0) == None
    assert mgr.phys_id_for(pid, 1) == None
    assert mgr.virt_id_for(pid, 0) == None
    assert mgr.virt_id_for(pid, 1) == None


def test_alloc_free_0_1():
    pid, mgr = setup_manager()

    assert mgr.phys_id_for(pid, 0) == None
    assert mgr.phys_id_for(pid, 1) == None
    assert mgr.virt_id_for(pid, 0) == None
    assert mgr.virt_id_for(pid, 1) == None

    mgr.allocate(pid, 0)
    mgr.allocate(pid, 1)
    assert mgr.phys_id_for(pid, 0) == 0
    assert mgr.phys_id_for(pid, 1) == 1
    assert mgr.virt_id_for(pid, 0) == 0
    assert mgr.virt_id_for(pid, 1) == 1

    mgr.free(pid, 0)
    assert mgr.phys_id_for(pid, 0) == None
    assert mgr.phys_id_for(pid, 1) == 1
    assert mgr.virt_id_for(pid, 0) == None
    assert mgr.virt_id_for(pid, 1) == 1


def test_alloc_non_existing():
    pid, mgr = setup_manager()

    with pytest.raises(AllocError):
        mgr.allocate(pid, 2)


if __name__ == "__main__":
    test_alloc_free_0()
    test_alloc_free_0_1()
    test_alloc_non_existing()
