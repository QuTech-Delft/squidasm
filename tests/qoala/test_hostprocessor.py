from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import netsquid as ns
from netqasm.lang.instr.core import SetInstruction
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import (
    AddCValueOp,
    AssignCValueOp,
    BitConditionalMultiplyConstantCValueOp,
    ClassicalIqoalaOp,
    IqoalaProgram,
    IqoalaSharedMemLoc,
    IqoalaSubroutine,
    IqoalaVector,
    MultiplyConstantCValueOp,
    ProgramMeta,
    ReceiveCMsgOp,
    ReturnResultOp,
    RunSubroutineOp,
    SendCMsgOp,
)
from squidasm.qoala.runtime.environment import (
    GlobalEnvironment,
    GlobalNodeInfo,
    LocalEnvironment,
)
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.hostprocessor import HostProcessor
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.util.tests import yield_from

MOCK_MESSAGE = Message(content=42)
MOCK_QNOS_RET_REG = "R0"
MOCK_QNOS_RET_VALUE = 7


@dataclass(eq=True, frozen=True)
class InterfaceEvent:
    peer: str
    msg: Message


class MockHostInterface(HostInterface):
    def __init__(self, shared_mem: Optional[SharedMemory] = None) -> None:
        self.send_events: List[InterfaceEvent] = []
        self.recv_events: List[InterfaceEvent] = []

        self.shared_mem = shared_mem

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        self.send_events.append(InterfaceEvent(peer, msg))

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        self.recv_events.append(InterfaceEvent(peer, MOCK_MESSAGE))
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    def send_qnos_msg(self, msg: Message) -> None:
        self.send_events.append(InterfaceEvent("qnos", msg))

    def receive_qnos_msg(self) -> Generator[EventExpression, None, Message]:
        self.recv_events.append(InterfaceEvent("qnos", MOCK_MESSAGE))
        if self.shared_mem is not None:
            self.shared_mem.set_reg_value(MOCK_QNOS_RET_REG, MOCK_QNOS_RET_VALUE)
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    @property
    def name(self) -> str:
        return "mock"


def create_program(
    instrs: Optional[List[ClassicalIqoalaOp]] = None,
    subroutines: Optional[Dict[str, IqoalaSubroutine]] = None,
    meta: Optional[ProgramMeta] = None,
) -> IqoalaProgram:
    if instrs is None:
        instrs = []
    if subroutines is None:
        subroutines = {}
    if meta is None:
        meta = ProgramMeta.empty("prog")
    return IqoalaProgram(instructions=instrs, subroutines=subroutines, meta=meta)


def create_process(
    program: IqoalaProgram,
    interface: HostInterface,
    inputs: Optional[Dict[str, Any]] = None,
) -> IqoalaProcess:
    if inputs is None:
        inputs = {}
    prog_input = ProgramInput(values=inputs)
    instance = ProgramInstance(pid=0, program=program, inputs=prog_input)
    mem = ProgramMemory(pid=0, unit_module=UnitModule.default_generic(2))
    process = IqoalaProcess(
        prog_instance=instance,
        prog_memory=mem,
        csockets={
            id: ClassicalSocket(interface, name)
            for (id, name) in program.meta.csockets.items()
        },
        epr_sockets=program.meta.epr_sockets,
        subroutines=program.subroutines,
        result=ProgramResult(values={}),
    )
    return process


def test_initialize():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program()
    process = create_process(
        program, interface, inputs={"x": 1, "theta": 3.14, "name": "alice"}
    )

    processor.initialize(process)
    host_mem = process.prog_memory.host_mem
    assert host_mem.read("x") == 1
    assert host_mem.read("theta") == 3.14
    assert host_mem.read("name") == "alice"


def test_assign_cvalue():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program(instrs=[AssignCValueOp("x", 3)])
    process = create_process(program, interface)
    processor.initialize(process)

    yield_from(processor.assign(process, 0))
    assert process.prog_memory.host_mem.read("x") == 3


def test_send_msg():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    meta = ProgramMeta.empty("alice")
    meta.csockets = {0: "bob"}
    program = create_program(instrs=[SendCMsgOp("bob", "msg")], meta=meta)
    process = create_process(program, interface, inputs={"bob": 0, "msg": 12})
    processor.initialize(process)

    yield_from(processor.assign(process, 0))
    assert interface.send_events[0] == InterfaceEvent("bob", Message(content=12))


def test_recv_msg():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    meta = ProgramMeta.empty("alice")
    meta.csockets = {0: "bob"}
    program = create_program(instrs=[ReceiveCMsgOp("bob", "msg")], meta=meta)
    process = create_process(program, interface, inputs={"bob": 0})
    processor.initialize(process)

    yield_from(processor.assign(process, 0))
    assert interface.recv_events[0] == InterfaceEvent("bob", MOCK_MESSAGE)
    assert process.prog_memory.host_mem.read("msg") == MOCK_MESSAGE.content


def test_add_cvalue():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program(
        instrs=[
            AssignCValueOp("a", 2),
            AssignCValueOp("b", 3),
            AddCValueOp("sum", "a", "b"),
        ]
    )
    process = create_process(program, interface)
    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert process.prog_memory.host_mem.read("sum") == 5


def test_multiply_const():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program(
        instrs=[AssignCValueOp("a", 4), MultiplyConstantCValueOp("result", "a", -1)]
    )
    process = create_process(program, interface)
    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert process.prog_memory.host_mem.read("result") == -4


def test_bit_cond_mult():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program(
        instrs=[
            AssignCValueOp("var1", 4),
            AssignCValueOp("var2", 7),
            AssignCValueOp("cond1", 0),
            AssignCValueOp("cond2", 1),
            BitConditionalMultiplyConstantCValueOp("result1", "var1", "cond1", -1),
            BitConditionalMultiplyConstantCValueOp("result2", "var2", "cond2", -1),
        ]
    )
    process = create_process(program, interface)
    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert process.prog_memory.host_mem.read("result1") == 4
    assert process.prog_memory.host_mem.read("result2") == -7


def test_run_subroutine():
    interface = MockHostInterface()
    processor = HostProcessor(interface)

    subrt = Subroutine()
    iqoala_subrt = IqoalaSubroutine("subrt1", subrt, return_map={})

    program = create_program(
        instrs=[RunSubroutineOp(IqoalaVector([]), "subrt1")],
        subroutines={"subrt1": iqoala_subrt},
    )
    process = create_process(program, interface)
    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert interface.send_events[0] == InterfaceEvent("qnos", Message("subrt1"))
    assert interface.recv_events[0] == InterfaceEvent("qnos", MOCK_MESSAGE)


def test_run_subroutine2():
    interface = MockHostInterface()
    processor = HostProcessor(interface)

    subrt_text = """
    set R0 {my_value}
    ret_reg R0
    """
    subrt = parse_text_subroutine(subrt_text)
    iqoala_subrt = IqoalaSubroutine(
        "subrt1", subrt, return_map={"m": IqoalaSharedMemLoc("R0")}
    )

    program = create_program(
        instrs=[
            AssignCValueOp("my_value", 16),
            RunSubroutineOp(IqoalaVector(["my_value"]), "subrt1"),
        ],
        subroutines={"subrt1": iqoala_subrt},
    )
    process = create_process(program, interface)

    # Make sure interface can mimick writing subroutine results to shared memory
    interface.shared_mem = process.prog_memory.shared_mem

    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert interface.send_events[0] == InterfaceEvent("qnos", Message("subrt1"))
    assert interface.recv_events[0] == InterfaceEvent("qnos", MOCK_MESSAGE)
    assert process.prog_memory.shared_mem.get_reg_value("R0") == MOCK_QNOS_RET_VALUE
    assert process.prog_memory.host_mem.read("m") == MOCK_QNOS_RET_VALUE


def test_return_result():
    interface = MockHostInterface()
    processor = HostProcessor(interface)
    program = create_program(
        instrs=[AssignCValueOp("result", 2), ReturnResultOp("result")]
    )
    process = create_process(program, interface)
    processor.initialize(process)

    for i in range(len(program.instructions)):
        yield_from(processor.assign(process, i))

    assert process.prog_memory.host_mem.read("result") == 2
    assert process.result.values == {"result": 2}


if __name__ == "__main__":
    test_initialize()
    test_assign_cvalue()
    test_send_msg()
    test_recv_msg()
    test_add_cvalue()
    test_multiply_const()
    test_bit_cond_mult()
    test_run_subroutine()
    test_run_subroutine2()
    test_return_result()
