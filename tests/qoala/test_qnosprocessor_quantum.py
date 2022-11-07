from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple

import netsquid as ns
import pytest
from netqasm.lang.operand import ArraySlice
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.sdk.build_epr import (
    SER_CREATE_IDX_NUMBER,
    SER_CREATE_IDX_ROTATION_X_REMOTE2,
    SER_CREATE_IDX_TYPE,
    SER_RESPONSE_KEEP_IDX_BELL_STATE,
    SER_RESPONSE_KEEP_IDX_GOODNESS,
    SER_RESPONSE_KEEP_LEN,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME,
    SER_RESPONSE_MEASURE_LEN,
)
from netsquid.components import instructions as ns_instr
from netsquid.components.qprocessor import MissingInstructionError, QuantumProcessor
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid.qubits import ketstates, qubitapi

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import IqoalaProgram, IqoalaSubroutine, ProgramMeta
from squidasm.qoala.runtime.config import GenericQDeviceConfig, NVQDeviceConfig
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.build import build_generic_qprocessor, build_nv_qprocessor
from squidasm.qoala.sim.common import NetstackCreateRequest, NetstackReceiveRequest
from squidasm.qoala.sim.constants import PI, PI_OVER_2
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, Topology, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import (
    GenericPhysicalQuantumMemory,
    NVPhysicalQuantumMemory,
    PhysicalQuantumMemory,
    QDevice,
    QDeviceCommand,
    QDeviceType,
    UnsupportedQDeviceCommandError,
)
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.util.tests import has_state, netsquid_run, yield_from


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


if __name__ == "__main__":
    test_init_qubit()
