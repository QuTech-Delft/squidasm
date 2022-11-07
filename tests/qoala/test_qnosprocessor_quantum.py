from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pytest
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.nodes import Node
from netsquid.qubits import ketstates

from squidasm.qoala.lang.iqoala import IqoalaProgram, IqoalaSubroutine, ProgramMeta
from squidasm.qoala.runtime.config import GenericQDeviceConfig
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.build import build_generic_qprocessor
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager, NotAllocatedError
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import (
    GenericPhysicalQuantumMemory,
    QDevice,
    QDeviceType,
)
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.util.tests import has_multi_state, has_state, netsquid_run


def perfect_generic_qdevice(num_qubits: int) -> QDevice:
    cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    processor = build_generic_qprocessor(name="processor", cfg=cfg)
    node = Node(name="alice", qmemory=processor)
    return QDevice(
        node=node,
        typ=QDeviceType.GENERIC,
        memory=GenericPhysicalQuantumMemory(num_qubits),
    )


def create_program(
    subroutines: Optional[Dict[str, IqoalaSubroutine]] = None,
    meta: Optional[ProgramMeta] = None,
) -> IqoalaProgram:
    if subroutines is None:
        subroutines = {}
    if meta is None:
        meta = ProgramMeta.empty("prog")
    return IqoalaProgram(instructions=[], subroutines=subroutines, meta=meta)


def create_process(
    pid: int, program: IqoalaProgram, unit_module: UnitModule
) -> IqoalaProcess:
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


def create_process_with_subrt(
    pid: int, subrt_text: str, unit_module: UnitModule
) -> IqoalaProcess:
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt", subrt, return_map={})
    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt": iqoala_subrt}, meta=meta)
    return create_process(pid, program, unit_module)


def set_new_subroutine(process: IqoalaProcess, subrt_text: str) -> None:
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt", subrt, return_map={})
    process.subroutines["subrt"] = iqoala_subrt


def execute_process(processor: GenericProcessor, process: IqoalaProcess) -> int:
    subroutines = process.prog_instance.program.subroutines
    netqasm_instructions = subroutines["subrt"].subroutine.instructions

    instr_count = 0

    instr_idx = 0
    while instr_idx < len(netqasm_instructions):
        instr_count += 1
        instr_idx = netsquid_run(processor.assign(process, "subrt", instr_idx))
    return instr_count


def execute_multiple_processes(
    processor: GenericProcessor, processes: List[IqoalaProcess]
) -> None:
    for proc in processes:
        subroutines = proc.prog_instance.program.subroutines
        netqasm_instructions = subroutines["subrt"].subroutine.instructions
        for i in range(len(netqasm_instructions)):
            netsquid_run(processor.assign(proc, "subrt", i))


def setup_components_generic(num_qubits: int) -> Tuple[QnosProcessor, UnitModule]:
    # TODO: SUPPORT ANY TOPOLOGY (ALSO REQUIRES REFACTORING CONFIG HANDLING)
    qdevice = perfect_generic_qdevice(num_qubits)
    unit_module = UnitModule.default_generic(num_qubits)
    qnos_comp = QnosComponent(node=qdevice._node)
    memmgr = MemoryManager(qdevice._node.name, qdevice)
    interface = QnosInterface(qnos_comp, qdevice, memmgr)
    processor = GenericProcessor(interface)
    return (processor, unit_module)


def test_init_qubit():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    subrt = """
    set Q0 0
    qalloc Q0
    init Q0
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    # Check if qubit with virt ID 0 has been initialized.
    phys_id = processor._interface.memmgr.phys_id_for(process.pid, virt_id=0)
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.s0)


def test_init_not_allocated():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    subrt = """
    set Q0 0
    init Q0
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)

    with pytest.raises(NotAllocatedError):
        execute_process(processor, process)


def test_alloc_no_init():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    subrt = """
    set Q0 0
    qalloc Q0
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    # Check if qubit with virt ID 0 has been initialized.
    phys_id = processor._interface.memmgr.phys_id_for(process.pid, virt_id=0)

    # The 'qalloc' should have created a mapping to a phys ID.
    assert phys_id is not None

    # However, no actual qubit state should have been initalized.
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert qubit is None


def test_single_gates_generic():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    subrt = """
    set Q0 0
    qalloc Q0
    init Q0
    x Q0
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    # Check if qubit with virt ID 0 has been initialized.
    phys_id = processor._interface.memmgr.phys_id_for(process.pid, virt_id=0)

    # Qubit should be in |1>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.s1)

    # New subroutine: apply X.
    subrt = """
    x Q0
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # Qubit should be back in |0>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.s0)

    # New subroutine: apply Z.
    subrt = """
    z Q0
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # Qubit should still be in |0>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.s0)

    # New subroutine: apply Z.
    subrt = """
    z Q0
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # Qubit should still be in |0>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.s0)

    # New subroutine: apply PI/2 Y-rotation.
    # pi/2 = 8 / 2^4 * pi
    subrt = """
    rot_y Q0 8 4
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # Qubit should be in |+>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.h0)

    # New subroutine: apply -PI/2 Z-rotation.
    # -pi/2 = 24 / 2^4 * pi
    subrt = """
    rot_z Q0 24 4
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # Qubit should be in |-i>
    qubit = processor.qdevice.get_local_qubit(phys_id)
    assert has_state(qubit, ketstates.y1)


def test_single_gates_multiple_qubits_generic():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    # Initialize q0 and q1. Apply X on q0 and Z on q1.
    subrt = """
    set Q0 0
    qalloc Q0
    init Q0
    set Q1 1
    qalloc Q1
    init Q1
    x Q0
    z Q1
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    # Check if qubit with virt ID 0 has been initialized.
    phys_id0 = processor._interface.memmgr.phys_id_for(process.pid, virt_id=0)
    # Check if qubit with virt ID 1 has been initialized.
    phys_id1 = processor._interface.memmgr.phys_id_for(process.pid, virt_id=1)

    # Virtual qubit 0 should be in |1>
    qubit0 = processor.qdevice.get_local_qubit(phys_id0)
    assert has_state(qubit0, ketstates.s1)

    # Virtual qubit 1 should be in |0>
    qubit1 = processor.qdevice.get_local_qubit(phys_id1)
    assert has_state(qubit1, ketstates.s0)

    # New subroutine: apply X to q0 and Y to q1
    subrt = """
    x Q0
    y Q1
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # q0 should be back in |0>
    qubit0 = processor.qdevice.get_local_qubit(phys_id0)
    assert has_state(qubit0, ketstates.s0)

    # q1 should be in |1>
    qubit1 = processor.qdevice.get_local_qubit(phys_id1)
    assert has_state(qubit1, ketstates.s1)

    # New subroutine: init q2, apply Y-rotation of PI/2 on q0
    # pi/2 = 8 / 2^4 * pi
    subrt = """
    set Q2 2
    qalloc Q2
    init Q2
    rot_y Q0 8 4
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # q0 should be in |+>
    qubit0 = processor.qdevice.get_local_qubit(phys_id0)
    assert has_state(qubit0, ketstates.h0)

    # q1 should still be in |1>
    qubit1 = processor.qdevice.get_local_qubit(phys_id1)
    assert has_state(qubit1, ketstates.s1)

    # Check if qubit with virt ID 2 has been initialized.
    phys_id2 = processor._interface.memmgr.phys_id_for(process.pid, virt_id=2)

    # q2 should be in |0>
    qubit2 = processor.qdevice.get_local_qubit(phys_id2)
    assert has_state(qubit2, ketstates.s0)


def test_two_qubit_gates_generic():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    # Initialize q0 and q1. Apply CNOT between q0 and q1.
    subrt = """
    set Q0 0
    qalloc Q0
    init Q0
    set Q1 1
    qalloc Q1
    init Q1
    cnot Q0 Q1
    """

    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    # Check if qubit with virt ID 0 has been initialized.
    phys_id0 = processor._interface.memmgr.phys_id_for(process.pid, virt_id=0)
    # Check if qubit with virt ID 1 has been initialized.
    phys_id1 = processor._interface.memmgr.phys_id_for(process.pid, virt_id=1)

    # Virtual qubit 0 should be in |0>
    q0 = processor.qdevice.get_local_qubit(phys_id0)
    assert has_state(q0, ketstates.s0)

    # Virtual qubit 1 should be in |0>
    q1 = processor.qdevice.get_local_qubit(phys_id1)
    assert has_state(q1, ketstates.s0)

    # New subroutine: apply H to q0 and again CNOT between q0 and q1
    subrt = """
    h Q0
    cnot Q0 Q1
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # q0 and q1 should be maximally entangled
    [q0, q1] = processor.qdevice.get_local_qubits([phys_id0, phys_id1])
    # TODO: fix fidelity calculation with mixed states
    # assert has_max_mixed_state(q0)
    assert has_multi_state([q0, q1], ketstates.b00)

    # New subroutine: apply CNOT between q1 and q0
    subrt = """
    cnot Q1 Q0
    """
    set_new_subroutine(process, subrt)
    execute_process(processor, process)

    # q0 should be |0>
    # q1 should be |+>
    [q0, q1] = processor.qdevice.get_local_qubits([phys_id0, phys_id1])
    assert has_state(q0, ketstates.s0)
    assert has_state(q1, ketstates.h0)


def test_multiple_processes_generic():
    num_qubits = 3
    processor, unit_module = setup_components_generic(num_qubits)

    # Process 0: initialize q0.
    subrt0 = """
    set Q0 0
    qalloc Q0
    init Q0
    """

    # Process 1: initialize q0.
    subrt1 = """
    set Q0 0
    qalloc Q0
    init Q0
    """

    process0 = create_process_with_subrt(0, subrt0, unit_module)
    process1 = create_process_with_subrt(1, subrt1, unit_module)
    processor._interface.memmgr.add_process(process0)
    processor._interface.memmgr.add_process(process1)
    execute_multiple_processes(processor, [process0, process1])

    # Check if qubit with virt ID 0 has been initialized for process 0
    proc0_phys_id0 = processor._interface.memmgr.phys_id_for(pid=0, virt_id=0)
    # Should be mapped to phys ID 0
    assert proc0_phys_id0 == 0

    # Check if qubit with virt ID 0 has been initialized for process 1
    proc1_phys_id0 = processor._interface.memmgr.phys_id_for(pid=1, virt_id=0)
    # Should be mapped to phys ID 1
    assert proc1_phys_id0 == 1

    # Process 0 virt qubit 0 should be in |0>
    proc0_q0 = processor.qdevice.get_local_qubit(proc0_phys_id0)
    assert has_state(proc0_q0, ketstates.s0)

    # Process 1 virt qubit 0 should be in |0>
    proc1_q0 = processor.qdevice.get_local_qubit(proc1_phys_id0)
    assert has_state(proc1_q0, ketstates.s0)

    # New subroutine for process 0: apply X to q0 and initialize q1
    subrt0 = """
    x Q0
    set Q1 1
    qalloc Q1
    init Q1
    """
    set_new_subroutine(process0, subrt0)

    # New subroutine for process 0: apply H to q0
    subrt1 = """
    h Q0
    """
    set_new_subroutine(process1, subrt1)
    execute_multiple_processes(processor, [process0, process1])

    # Check if qubit with virt ID 1 has been initialized for process 0
    proc0_phys_id1 = processor._interface.memmgr.phys_id_for(pid=0, virt_id=1)
    # Should be mapped to phys ID 2
    assert proc0_phys_id1 == 2

    # Process 0 virt qubit 0 should be in |1>
    proc0_q0 = processor.qdevice.get_local_qubit(proc0_phys_id0)
    assert has_state(proc0_q0, ketstates.s1)

    # Process 0 virt qubit 1 should be in |0>
    proc0_q1 = processor.qdevice.get_local_qubit(proc0_phys_id1)
    assert has_state(proc0_q1, ketstates.s0)

    # Process 1 virt qubit 0 should be in |+>
    proc1_q0 = processor.qdevice.get_local_qubit(proc1_phys_id0)
    assert has_state(proc1_q0, ketstates.h0)

    # New subroutine for process 1: alloc q1
    subrt1 = """
    set Q1 1
    qalloc Q1
    init Q1
    """
    set_new_subroutine(process1, subrt1)
    # Should raise an AllocError since no physical qubits left.
    with pytest.raises(AllocError):
        execute_multiple_processes(processor, [process0, process1])

    # New subroutine for process 0: free q0
    subrt0 = """
    qfree Q0
    """
    set_new_subroutine(process0, subrt0)
    # Try again same subroutine for process 1
    execute_multiple_processes(processor, [process0, process1])

    # Check that qubit with virt ID 0 has been freed for process 0
    assert processor._interface.memmgr.phys_id_for(pid=0, virt_id=0) is None

    # Check that qubit with virt ID 1 for process 0 is still mapped to phys ID 2
    assert processor._interface.memmgr.phys_id_for(pid=0, virt_id=1) == 2

    # Check that qubit with virt ID 0 for process 1 is still mapped to phys ID 1
    assert processor._interface.memmgr.phys_id_for(pid=1, virt_id=0) == 1

    # Check that qubit with virt ID 1 for process 1 is now mapped to phys ID 0
    assert processor._interface.memmgr.phys_id_for(pid=1, virt_id=1) == 0

    # Check that physical qubit 0 has been reset to |0>
    # (because of initializing virt qubit 1 in process 1)
    phys_qubit_0 = processor.qdevice.get_local_qubit(0)
    assert has_state(phys_qubit_0, ketstates.s0)


if __name__ == "__main__":
    test_init_qubit()
    test_init_not_allocated()
    test_alloc_no_init()
    test_single_gates_generic()
    test_single_gates_multiple_qubits_generic()
    test_two_qubit_gates_generic()
    test_multiple_processes_generic()
