from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple

import pytest
from netqasm.lang.parsing import parse_text_subroutine

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import IqoalaProgram, IqoalaSubroutine, ProgramMeta
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, Topology, UnitModule
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


def create_process_with_subrt(
    pid: int, subrt_text: str, unit_module: UnitModule
) -> IqoalaProcess:
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt", subrt, return_map={})
    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt": iqoala_subrt}, meta=meta)
    return create_process(pid, program, unit_module)


def execute_process(processor: GenericProcessor, process: IqoalaProcess) -> None:
    subroutines = process.prog_instance.program.subroutines
    netqasm_instructions = subroutines["subrt"].subroutine.instructions
    for i in range(len(netqasm_instructions)):
        yield_from(processor.assign(process, "subrt", i))


def execute_multiple_processes(
    processor: GenericProcessor, processes: List[IqoalaProcess]
) -> None:
    for proc in processes:
        subroutines = proc.prog_instance.program.subroutines
        netqasm_instructions = subroutines["subrt"].subroutine.instructions
        for i in range(len(netqasm_instructions)):
            yield_from(processor.assign(proc, "subrt", i))


def setup_components(topology: Topology) -> Tuple[QnosProcessor, UnitModule]:
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    interface = MockQnosInterface(qdevice)
    processor = QnosProcessor(interface)
    return (processor, unit_module)


def test_set_reg():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set R0 17
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)
    assert process.prog_memory.shared_mem.get_reg_value("R0") == 17


def test_add():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set R0 2
    set R1 5
    add R2 R0 R1
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)
    assert process.prog_memory.shared_mem.get_reg_value("R2") == 7


def test_alloc_qubit():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set Q0 0
    qalloc Q0
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    assert processor._interface.memmgr.phys_id_for(process.pid, 0) == 0
    assert processor._interface.memmgr.phys_id_for(process.pid, 1) is None


def test_free_qubit():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set Q0 0
    qalloc Q0
    qfree Q0
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    assert processor._interface.memmgr.phys_id_for(process.pid, 0) is None
    assert processor._interface.memmgr.phys_id_for(process.pid, 1) is None


def test_free_non_allocated():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set Q0 0
    qfree Q0
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)

    with pytest.raises(AllocError):
        execute_process(processor, process)


def test_alloc_multiple():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt = """
    set Q0 0
    set Q1 1
    qalloc Q0
    qalloc Q1
    """
    process = create_process_with_subrt(0, subrt, unit_module)
    processor._interface.memmgr.add_process(process)
    execute_process(processor, process)

    assert processor._interface.memmgr.phys_id_for(process.pid, 0) == 0
    assert processor._interface.memmgr.phys_id_for(process.pid, 1) == 1


def test_alloc_multiprocess():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={1}))

    subrt0 = """
    set Q0 0
    qalloc Q0
    """
    subrt1 = """
    set Q1 1
    qalloc Q1
    """
    process0 = create_process_with_subrt(0, subrt0, unit_module)
    process1 = create_process_with_subrt(1, subrt1, unit_module)
    processor._interface.memmgr.add_process(process0)
    processor._interface.memmgr.add_process(process1)
    execute_multiple_processes(processor, [process0, process1])

    assert processor._interface.memmgr.phys_id_for(process0.pid, 0) == 0
    assert processor._interface.memmgr.phys_id_for(process0.pid, 1) is None
    assert processor._interface.memmgr.phys_id_for(process1.pid, 0) is None
    assert processor._interface.memmgr.phys_id_for(process1.pid, 1) == 1

    assert processor._interface.memmgr._physical_mapping[0].pid == process0.pid
    assert processor._interface.memmgr._physical_mapping[1].pid == process1.pid


def test_alloc_multiprocess_same_virt_id():
    processor, unit_module = setup_components(Topology(comm_ids={0, 1}, mem_ids={0, 1}))

    subrt0 = """
    set Q0 0
    qalloc Q0
    """
    subrt1 = """
    set Q0 0
    qalloc Q0
    """

    process0 = create_process_with_subrt(0, subrt0, unit_module)
    process1 = create_process_with_subrt(1, subrt1, unit_module)
    processor._interface.memmgr.add_process(process0)
    processor._interface.memmgr.add_process(process1)
    execute_multiple_processes(processor, [process0, process1])

    assert processor._interface.memmgr.phys_id_for(process0.pid, 0) == 0
    assert processor._interface.memmgr.phys_id_for(process0.pid, 1) is None
    assert processor._interface.memmgr.phys_id_for(process1.pid, 0) == 1
    assert processor._interface.memmgr.phys_id_for(process1.pid, 1) is None

    assert processor._interface.memmgr._physical_mapping[0].pid == process0.pid
    assert processor._interface.memmgr._physical_mapping[1].pid == process1.pid


def test_alloc_multiprocess_same_virt_id_trait_not_available():
    processor, unit_module = setup_components(Topology(comm_ids={0}, mem_ids={0, 1}))

    subrt0 = """
    set Q0 0
    qalloc Q0
    """
    subrt1 = """
    set Q0 0
    qalloc Q0
    """

    process0 = create_process_with_subrt(0, subrt0, unit_module)
    process1 = create_process_with_subrt(1, subrt1, unit_module)
    processor._interface.memmgr.add_process(process0)
    processor._interface.memmgr.add_process(process1)

    with pytest.raises(AllocError):
        execute_multiple_processes(processor, [process0, process1])


if __name__ == "__main__":
    test_set_reg()
    test_add()
    test_alloc_qubit()
    test_free_qubit()
    test_free_non_allocated()
    test_alloc_multiple()
    test_alloc_multiprocess()
    test_alloc_multiprocess_same_virt_id()
    test_alloc_multiprocess_same_virt_id_trait_not_available()
