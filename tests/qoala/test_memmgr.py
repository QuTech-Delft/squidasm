from __future__ import annotations

from typing import List, Set, Tuple

import pytest

from squidasm.qoala.lang.iqoala import IqoalaProgram, ProgramMeta
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import (
    CommQubitTrait,
    MemQubitTrait,
    ProgramMemory,
    UnitModule,
)
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice


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


def create_process(pid: int, unit_module: UnitModule) -> IqoalaProcess:
    program = IqoalaProgram(
        instructions=[], subroutines={}, meta=ProgramMeta.empty("prog")
    )
    instance = ProgramInstance(pid=pid, program=program, inputs=ProgramInput({}))
    mem = ProgramMemory(pid=pid, unit_module=unit_module)

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

    process = create_process(0, um)
    mgr.add_process(process)
    pid = process.pid

    return pid, mgr


def setup_manager_multiple_processes(
    num_processes: int,
) -> Tuple[List[int], MemoryManager]:
    qdevice = MockQDevice()
    mgr = MemoryManager("alice", qdevice)

    um = UnitModule(
        qubit_ids=[0, 1],
        qubit_traits={0: [CommQubitTrait], 1: [MemQubitTrait]},
        gate_traits={},
    )

    pids: List[int] = []

    for i in range(num_processes):
        process = create_process(i, um)
        mgr.add_process(process)
        pids.append(process.pid)

    return pids, mgr


def test_alloc_free_0():
    pid, mgr = setup_manager()

    assert mgr.phys_id_for(pid, 0) is None
    assert mgr.phys_id_for(pid, 1) is None
    assert mgr.virt_id_for(pid, 0) is None
    assert mgr.virt_id_for(pid, 1) is None

    mgr.allocate(pid, 0)
    assert mgr.phys_id_for(pid, 0) == 0
    assert mgr.phys_id_for(pid, 1) is None
    assert mgr.virt_id_for(pid, 0) == 0
    assert mgr.virt_id_for(pid, 1) is None

    mgr.free(pid, 0)
    assert mgr.phys_id_for(pid, 0) is None
    assert mgr.phys_id_for(pid, 1) is None
    assert mgr.virt_id_for(pid, 0) is None
    assert mgr.virt_id_for(pid, 1) is None


def test_alloc_free_0_1():
    pid, mgr = setup_manager()

    assert mgr.phys_id_for(pid, 0) is None
    assert mgr.phys_id_for(pid, 1) is None
    assert mgr.virt_id_for(pid, 0) is None
    assert mgr.virt_id_for(pid, 1) is None

    mgr.allocate(pid, 0)
    mgr.allocate(pid, 1)
    assert mgr.phys_id_for(pid, 0) == 0
    assert mgr.phys_id_for(pid, 1) == 1
    assert mgr.virt_id_for(pid, 0) == 0
    assert mgr.virt_id_for(pid, 1) == 1

    mgr.free(pid, 0)
    assert mgr.phys_id_for(pid, 0) is None
    assert mgr.phys_id_for(pid, 1) == 1
    assert mgr.virt_id_for(pid, 0) is None
    assert mgr.virt_id_for(pid, 1) == 1


def test_alloc_non_existing():
    pid, mgr = setup_manager()

    with pytest.raises(AllocError):
        mgr.allocate(pid, 2)


def test_alloc_already_allocated():
    pid, mgr = setup_manager()

    with pytest.raises(AllocError):
        mgr.allocate(pid, 1)
        mgr.allocate(pid, 1)


def test_free_alreay_freed():
    pid, mgr = setup_manager()

    with pytest.raises(AllocError):
        mgr.free(pid, 0)


def test_get_unmapped_qubit():
    pid, mgr = setup_manager()

    assert mgr.get_unmapped_mem_qubit(pid) == 1
    mgr.allocate(pid, 0)
    assert mgr.get_unmapped_mem_qubit(pid) == 1
    mgr.allocate(pid, 1)
    with pytest.raises(AllocError):
        mgr.get_unmapped_mem_qubit(pid)
    mgr.free(pid, 1)
    assert mgr.get_unmapped_mem_qubit(pid) == 1


def test_alloc_multiple_processes():
    [pid0, pid1], mgr = setup_manager_multiple_processes(2)

    assert mgr.phys_id_for(pid0, 0) is None
    assert mgr.phys_id_for(pid0, 1) is None
    assert mgr.virt_id_for(pid0, 0) is None
    assert mgr.virt_id_for(pid0, 1) is None
    assert mgr.phys_id_for(pid1, 0) is None
    assert mgr.phys_id_for(pid1, 1) is None
    assert mgr.virt_id_for(pid1, 0) is None
    assert mgr.virt_id_for(pid1, 1) is None

    mgr.allocate(pid0, 0)
    # Should allocate phys ID 0 for virt ID 0 of pid0
    assert mgr.phys_id_for(pid0, 0) == 0
    assert mgr.virt_id_for(pid0, 0) == 0

    with pytest.raises(AllocError):
        # Should try to allocate phys ID 0, but it's not available
        mgr.allocate(pid1, 0)

    mgr.allocate(pid1, 1)
    # Should have mapping:
    #   phys ID 0 : (pid0, virt0)
    #   phys ID 1 : (pid1, virt1)
    assert mgr.phys_id_for(pid0, 0) == 0
    assert mgr.phys_id_for(pid0, 1) is None
    assert mgr.virt_id_for(pid0, 0) == 0
    assert mgr.virt_id_for(pid0, 1) is None
    assert mgr.phys_id_for(pid1, 0) is None
    assert mgr.phys_id_for(pid1, 1) == 1
    assert mgr.virt_id_for(pid1, 0) is None
    assert mgr.virt_id_for(pid1, 1) == 1


if __name__ == "__main__":
    test_alloc_free_0()
    test_alloc_free_0_1()
    test_alloc_non_existing()
    test_alloc_already_allocated()
    test_free_alreay_freed()
    test_get_unmapped_qubit()
    test_alloc_multiple_processes()
