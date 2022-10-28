from __future__ import annotations

from code import interact
from dataclasses import dataclass
from re import M
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

MOCK_MESSAGE = Message(content=42)
MOCK_QNOS_RET_REG = "R0"
MOCK_QNOS_RET_VALUE = 7


@dataclass(eq=True, frozen=True)
class InterfaceEvent:
    peer: str
    msg: Message


@dataclass(eq=True, frozen=True)
class FlushEvent:
    pass


@dataclass(eq=True, frozen=True)
class SignalEvent:
    pass


@dataclass
class Topology:
    comm_ids: Set[int]
    mem_ids: Set[int]


def create_unit_module(topology: Topology) -> UnitModule:
    all_ids = topology.comm_ids.union(topology.mem_ids)
    traits = {i: [] for i in all_ids}
    for i in all_ids:
        if i in topology.comm_ids:
            traits[i].append(CommQubitTrait)
        if i in topology.mem_ids:
            traits[i].append(MemQubitTrait)
    return UnitModule(qubit_ids=list(all_ids), qubit_traits=traits, gate_traits={})


class MockQDevice(QDevice):
    def __init__(self, topology: Topology) -> None:
        self._memory = PhysicalQuantumMemory(topology.comm_ids, topology.mem_ids)

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        pass


class MockQnosInterface(QnosInterface):
    def __init__(self, qdevice: QDevice) -> None:
        self.send_events: List[InterfaceEvent] = []
        self.recv_events: List[InterfaceEvent] = []
        self.flush_events: List[FlushEvent] = []
        self.signal_events: List[SignalEvent] = []

        self._qdevice = qdevice
        self._memmgr = MemoryManager("alice", self._qdevice)

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        self.send_events.append(InterfaceEvent(peer, msg))

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        self.recv_events.append(InterfaceEvent(peer, MOCK_MESSAGE))
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    def send_host_msg(self, msg: Message) -> None:
        self.send_events.append(InterfaceEvent("host", msg))

    def receive_host_msg(self) -> Generator[EventExpression, None, Message]:
        self.recv_events.append(InterfaceEvent("host", MOCK_MESSAGE))
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    def send_netstack_msg(self, msg: Message) -> None:
        self.send_events.append(InterfaceEvent("netstack", msg))

    def receive_netstack_msg(self) -> Generator[EventExpression, None, Message]:
        self.recv_events.append(InterfaceEvent("netstack", MOCK_MESSAGE))
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    def flush_netstack_msgs(self) -> None:
        self.flush_events.append(FlushEvent())

    def signal_memory_freed(self) -> None:
        self.signal_events.append(SignalEvent())

    @property
    def name(self) -> str:
        return "mock"


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


def execute_subroutine(
    processor: GenericProcessor,
    interface: QnosInterface,
    text: str,
    unit_module: UnitModule,
) -> IqoalaProcess:
    subrt = parse_text_subroutine(text)
    iqoala_subrt = IqoalaSubroutine("subrt1", subrt, return_map={})
    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt1": iqoala_subrt}, meta=meta)
    process = create_process(0, program, unit_module)
    interface.memmgr.add_process(process)

    netqasm_instructions = program.subroutines["subrt1"].subroutine.instructions
    for i in range(len(netqasm_instructions)):
        yield_from(processor.assign(process, "subrt1", i))

    return process


def execute_multiple_subroutines(
    processor: GenericProcessor,
    interface: QnosInterface,
    text1: str,
    text2: str,
    unit_module1: UnitModule,
    unit_module2: UnitModule,
) -> Tuple[IqoalaProcess, IqoalaProcess]:
    subrt1 = parse_text_subroutine(text1)
    subrt2 = parse_text_subroutine(text2)
    iqoala_subrt1 = IqoalaSubroutine("subrt1", subrt1, return_map={})
    iqoala_subrt2 = IqoalaSubroutine("subrt2", subrt2, return_map={})
    meta1 = ProgramMeta.empty("alice1")
    meta1.epr_sockets = {0: "bob"}
    meta2 = ProgramMeta.empty("alice2")
    meta2.epr_sockets = {0: "bob"}
    program1 = create_program(subroutines={"subrt1": iqoala_subrt1}, meta=meta1)
    program2 = create_program(subroutines={"subrt2": iqoala_subrt2}, meta=meta1)
    process1 = create_process(1, program1, unit_module1)
    process2 = create_process(2, program2, unit_module2)
    interface.memmgr.add_process(process1)
    interface.memmgr.add_process(process2)

    netqasm_instructions1 = program1.subroutines["subrt1"].subroutine.instructions
    netqasm_instructions2 = program2.subroutines["subrt2"].subroutine.instructions
    for i in range(len(netqasm_instructions1)):
        yield_from(processor.assign(process1, "subrt1", i))
    for i in range(len(netqasm_instructions2)):
        yield_from(processor.assign(process2, "subrt2", i))

    return [process1, process2]


def test_create_unit_module():
    top = Topology(comm_ids={0}, mem_ids={0})
    um = create_unit_module(top)

    assert um == UnitModule(
        qubit_ids=[0], qubit_traits={0: [CommQubitTrait, MemQubitTrait]}, gate_traits={}
    )


def test_set_reg():
    qdevice = MockQDevice()
    interface = MockQnosInterface(qubit_count=2)
    processor = QnosProcessor(interface)

    subrt = """
    set R0 17
    """
    process = execute_subroutine(processor, interface, subrt)
    assert process.prog_memory.shared_mem.get_reg_value("R0") == 17


def test_add():
    interface = MockQnosInterface(qubit_count=2)
    processor = QnosProcessor(interface)

    subrt = """
    set R0 2
    set R1 5
    add R2 R0 R1
    """
    process = execute_subroutine(subrt, interface, processor)
    assert process.prog_memory.shared_mem.get_reg_value("R2") == 7


def test_alloc_qubit():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt = """
    set Q0 0
    qalloc Q0
    """
    process = execute_subroutine(subrt, interface, processor)

    assert interface.memmgr.phys_id_for(process.pid, 0) == 0
    assert interface.memmgr.phys_id_for(process.pid, 1) == None


def test_free_qubit():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt = """
    set Q0 0
    qalloc Q0
    qfree Q0
    """
    process = execute_subroutine(subrt, interface, processor)

    assert interface.memmgr.phys_id_for(process.pid, 0) == None
    assert interface.memmgr.phys_id_for(process.pid, 1) == None


def test_free_non_allocated():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt = """
    set Q0 0
    qfree Q0
    """
    with pytest.raises(AllocError):
        execute_subroutine(subrt, interface, processor)


def test_alloc_multiple():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt = """
    set Q0 0
    set Q1 1
    qalloc Q0
    qalloc Q1
    """
    process = execute_subroutine(subrt, interface, processor)

    assert interface.memmgr.phys_id_for(process.pid, 0) == 0
    assert interface.memmgr.phys_id_for(process.pid, 1) == 1


def test_alloc_multiprocess():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt1 = """
    set Q0 0
    qalloc Q0
    """
    subrt2 = """
    set Q1 1
    qalloc Q1
    """
    process1, process2 = execute_multiple_subroutines(
        subrt1, subrt2, interface, processor
    )

    assert interface.memmgr.phys_id_for(process1.pid, 0) == 0
    assert interface.memmgr.phys_id_for(process1.pid, 1) == None
    assert interface.memmgr.phys_id_for(process2.pid, 0) == None
    assert interface.memmgr.phys_id_for(process2.pid, 1) == 1

    assert interface.memmgr._physical_mapping[0].pid == process1.pid
    assert interface.memmgr._physical_mapping[1].pid == process2.pid


def test_alloc_multiprocess_same_virt_id():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt1 = """
    set Q0 0
    qalloc Q0
    """
    subrt2 = """
    set Q0 0
    qalloc Q0
    """

    process1, process2 = execute_multiple_subroutines(
        subrt1, subrt2, interface, processor
    )

    assert interface.memmgr.phys_id_for(process1.pid, 0) == 0
    assert interface.memmgr.phys_id_for(process1.pid, 1) == None
    assert interface.memmgr.phys_id_for(process2.pid, 0) == 1
    assert interface.memmgr.phys_id_for(process2.pid, 1) == None

    assert interface.memmgr._physical_mapping[0].pid == process1.pid
    assert interface.memmgr._physical_mapping[1].pid == process2.pid


if __name__ == "__main__":
    # test_set_reg()
    # test_add()
    # test_alloc_qubit()
    # test_free_qubit()
    # test_free_non_allocated()
    # test_alloc_multiple()
    # test_alloc_multiprocess()
    # test_alloc_multiprocess_same_virt_id()
    test_create_unit_module()
