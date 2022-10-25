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
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, UnitModule
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
    def __init__(self, qubit_count: int) -> None:
        self._memory = PhysicalQuantumMemory(qubit_count)


class MockQnosInterface(QnosInterface):
    def __init__(self, qubit_count: int) -> None:
        self.send_events: List[InterfaceEvent] = []
        self.recv_events: List[InterfaceEvent] = []
        self.flush_events: List[FlushEvent] = []
        self.signal_events: List[SignalEvent] = []

        self._qdevice = MockQDevice(qubit_count=qubit_count)

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
    program: IqoalaProgram,
) -> IqoalaProcess:
    instance = ProgramInstance(pid=0, program=program, inputs=ProgramInput({}))
    mem = ProgramMemory(pid=0, unit_module=UnitModule.default_generic(2))

    process = IqoalaProcess(
        prog_instance=instance,
        prog_memory=mem,
        csockets={},
        epr_sockets=program.meta.epr_sockets,
        subroutines=program.subroutines,
        result=ProgramResult(values={}),
    )
    return process


def test_set_reg():
    interface = MockQnosInterface()
    processor = QnosProcessor(interface)

    subrt_text = """
    set R0 17
    """
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt1", subrt, return_map={})

    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt1": iqoala_subrt}, meta=meta)
    process = create_process(program)

    netqasm_instructions = program.subroutines["subrt1"].subroutine.instructions
    for i in range(len(netqasm_instructions)):
        yield_from(processor.assign(process, "subrt1", i))

    assert process.prog_memory.shared_mem.get_reg_value("R0") == 17


def test_add():
    interface = MockQnosInterface()
    processor = QnosProcessor(interface)

    subrt_text = """
    set R0 2
    set R1 5
    add R2 R0 R1
    """
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt1", subrt, return_map={})

    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt1": iqoala_subrt}, meta=meta)
    process = create_process(program)

    netqasm_instructions = program.subroutines["subrt1"].subroutine.instructions
    for i in range(len(netqasm_instructions)):
        yield_from(processor.assign(process, "subrt1", i))

    assert process.prog_memory.shared_mem.get_reg_value("R2") == 7


def test_alloc_qubit():
    interface = MockQnosInterface(qubit_count=2)
    processor = GenericProcessor(interface)

    subrt_text = """
    set Q0 0
    qalloc Q0
    """
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine("subrt1", subrt, return_map={})

    meta = ProgramMeta.empty("alice")
    meta.epr_sockets = {0: "bob"}
    program = create_program(subroutines={"subrt1": iqoala_subrt}, meta=meta)
    process = create_process(program)

    netqasm_instructions = program.subroutines["subrt1"].subroutine.instructions
    for i in range(len(netqasm_instructions)):
        yield_from(processor.assign(process, "subrt1", i))

    assert process.prog_memory.quantum_mem.qubit_mapping == {0: 0, 1: None}


if __name__ == "__main__":
    # test_set_reg()
    # test_add()
    test_alloc_qubit()
