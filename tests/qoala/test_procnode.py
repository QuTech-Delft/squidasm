from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple, Type

import netsquid as ns
import pytest
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
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
from netsquid.components import QuantumProcessor
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid.qubits import ketstates
from netsquid.qubits.ketstates import BellIndex
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    DepolariseWithFailureMagicDistributor,
    DoubleClickMagicDistributor,
    PerfectStateMagicDistributor,
)
from qlink_interface import (
    ReqCreateAndKeep,
    ReqCreateBase,
    ReqMeasureDirectly,
    ReqReceive,
    ReqRemoteStatePrep,
    ResCreateAndKeep,
)
from qlink_interface.interface import ResCreate

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import (
    AddCValueOp,
    AssignCValueOp,
    BitConditionalMultiplyConstantCValueOp,
    ClassicalIqoalaOp,
    IqoalaProgram,
    IqoalaSharedMemLoc,
    IqoalaSubroutine,
    IQoalaSubroutineParser,
    IqoalaVector,
    MultiplyConstantCValueOp,
    ProgramMeta,
    ReceiveCMsgOp,
    ReturnResultOp,
    RunSubroutineOp,
    SendCMsgOp,
)
from squidasm.qoala.runtime.config import GenericQDeviceConfig
from squidasm.qoala.runtime.environment import (
    GlobalEnvironment,
    GlobalNodeInfo,
    LocalEnvironment,
)
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.build import build_generic_qprocessor
from squidasm.qoala.sim.constants import PI
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.hostprocessor import HostProcessor
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, Topology, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnode import ProcNode
from squidasm.qoala.sim.qdevice import (
    PhysicalQuantumMemory,
    QDevice,
    QDeviceCommand,
    QDeviceType,
)
from squidasm.qoala.sim.qnos import Qnos
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.qoala.sim.requests import (
    EprCreateType,
    NetstackCreateRequest,
    NetstackReceiveRequest,
)
from squidasm.util.tests import has_multi_state, has_state, netsquid_run, yield_from

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


class MockNetstackInterface(NetstackInterface):
    def __init__(
        self,
        local_env: LocalEnvironment,
        qdevice: QDevice,
        memmgr: MemoryManager,
        mock_result: ResCreate,
    ) -> None:
        self._qdevice = qdevice
        self._local_env = local_env
        self._memmgr = memmgr
        self._mock_result = mock_result

        self._requests_put: Dict[int, List[ReqCreateBase]] = {}
        self._awaited_result_ck: List[int] = []  # list of remote ids
        self._awaited_mem_free_sig_count: int = 0

    def put_request(self, remote_id: int, request: ReqCreateBase) -> None:
        if remote_id not in self._requests_put:
            self._requests_put[remote_id] = []
        self._requests_put[remote_id].append(request)

    def await_result_create_keep(
        self, remote_id: int
    ) -> Generator[EventExpression, None, ResCreateAndKeep]:
        self._awaited_result_ck.append(remote_id)
        return self._mock_result
        yield  # to make this behave as a generator

    def await_memory_freed_signal(
        self, pid: int, virt_id: int
    ) -> Generator[EventExpression, None, None]:
        raise AllocError
        yield  # to make this behave as a generator

    def send_qnos_msg(self, msg: Message) -> None:
        return None

    def send_peer_msg(self, peer: str, msg: Message) -> None:
        return None

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, Message]:
        return None
        yield  # to make this behave as a generator

    def reset(self) -> None:
        self._requests_put = {}
        self._awaited_result_ck = []
        self._awaited_mem_free_sig_count = 0


class MockQDevice(QDevice):
    def __init__(self, topology: Topology) -> None:
        self._memory = PhysicalQuantumMemory(topology.comm_ids, topology.mem_ids)

        self._executed_commands: List[QDeviceCommand] = []

    @property
    def typ(self) -> QDeviceType:
        return QDeviceType.GENERIC

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        pass

    def execute_commands(
        self, commands: List[QDeviceCommand]
    ) -> Generator[EventExpression, None, Optional[int]]:
        self._executed_commands.extend(commands)
        return None
        yield

    def reset(self) -> None:
        self._executed_commands = []


@dataclass
class MockNetstackResultInfo:
    pid: int
    array_id: int
    start_idx: int
    end_idx: int


class MockQnosInterface(QnosInterface):
    def __init__(
        self,
        qdevice: QDevice,
        netstack_result_info: Optional[MockNetstackResultInfo] = None,
    ) -> None:
        self.send_events: List[InterfaceEvent] = []
        self.recv_events: List[InterfaceEvent] = []
        self.flush_events: List[FlushEvent] = []
        self.signal_events: List[SignalEvent] = []

        self._qdevice = qdevice
        self._memmgr = MemoryManager("alice", self._qdevice)

        self.netstack_result_info: Optional[
            MockNetstackResultInfo
        ] = netstack_result_info

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
        if self.netstack_result_info is not None:
            mem = self.memmgr._processes[
                self.netstack_result_info.pid
            ].prog_memory.shared_mem
            array_id = self.netstack_result_info.array_id
            start_idx = self.netstack_result_info.start_idx
            end_idx = self.netstack_result_info.end_idx
            for i in range(start_idx, end_idx):
                mem.set_array_value(array_id, i, 42)
        return MOCK_MESSAGE
        yield  # to make it behave as a generator

    def flush_netstack_msgs(self) -> None:
        self.flush_events.append(FlushEvent())

    def signal_memory_freed(self) -> None:
        self.signal_events.append(SignalEvent())

    @property
    def name(self) -> str:
        return "mock"


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
    pid: int,
    program: IqoalaProgram,
    unit_module: UnitModule,
    host_interface: HostInterface,
    inputs: Optional[Dict[str, Any]] = None,
) -> IqoalaProcess:
    if inputs is None:
        inputs = {}
    prog_input = ProgramInput(values=inputs)
    instance = ProgramInstance(pid=pid, program=program, inputs=prog_input)
    mem = ProgramMemory(pid=0, unit_module=unit_module)

    process = IqoalaProcess(
        prog_instance=instance,
        prog_memory=mem,
        csockets={
            id: ClassicalSocket(host_interface, name)
            for (id, name) in program.meta.csockets.items()
        },
        epr_sockets=program.meta.epr_sockets,
        subroutines=program.subroutines,
        result=ProgramResult(values={}),
    )
    return process


def create_qprocessor(name: str, num_qubits: int) -> QuantumProcessor:
    cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    return build_generic_qprocessor(name=f"{name}_processor", cfg=cfg)


def create_global_env(num_qubits: int) -> GlobalEnvironment:
    alice_node_id = 0
    bob_node_id = 1
    charlie_node_id = 2

    env = GlobalEnvironment()
    env.add_node(
        alice_node_id, GlobalNodeInfo.default_nv("alice", alice_node_id, num_qubits)
    )
    env.add_node(bob_node_id, GlobalNodeInfo.default_nv("bob", bob_node_id, num_qubits))
    env.add_node(
        charlie_node_id,
        GlobalNodeInfo.default_nv("charlie", charlie_node_id, num_qubits),
    )

    return env


def create_procnode(
    name: str,
    env: GlobalEnvironment,
    num_qubits: int,
    procnode_cls: Type[ProcNode] = ProcNode,
    asynchronous: bool = False,
) -> ProcNode:
    alice_qprocessor = create_qprocessor(name, num_qubits)

    node_id = env.get_node_id(name)
    procnode = procnode_cls(
        name=name,
        global_env=env,
        qprocessor=alice_qprocessor,
        node_id=node_id,
        asynchronous=asynchronous,
    )

    return procnode


def simple_subroutine(name: str, subrt_text: str) -> IqoalaSubroutine:
    subrt = parse_text_subroutine(subrt_text)
    return IqoalaSubroutine(name, subrt, return_map={})


def parse_iqoala_subroutines(subrt_text: str) -> IqoalaSubroutine:
    return IQoalaSubroutineParser(subrt_text).parse()


def create_egp_protocols(node1: Node, node2: Node) -> Tuple[EgpProtocol, EgpProtocol]:
    link_dist = PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=1000.0)
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[node1, node2],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    return EgpProtocol(node1, link_prot), EgpProtocol(node2, link_prot)


def test_initialize():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)
    local_env = LocalEnvironment(global_env, global_env.get_node_id("alice"))
    procnode = create_procnode("alice", global_env, num_qubits)
    procnode.qdevice = MockQDevice(topology)

    procnode.host.interface = MockHostInterface()

    mock_result = ResCreateAndKeep(bell_state=BellIndex.B01)
    procnode.netstack.interface = MockNetstackInterface(
        local_env, procnode.qdevice, procnode.memmgr, mock_result
    )

    host_processor = procnode.host.processor
    qnos_processor = procnode.qnos.processor
    netstack_processor = procnode.netstack.processor

    unit_module = UnitModule.default_generic(num_qubits)

    instrs = [AssignCValueOp("x", 3)]
    subrt1 = simple_subroutine(
        "subrt1",
        """
    set R5 42
    """,
    )

    program = create_program(instrs=instrs, subroutines={"subrt1": subrt1})
    process = create_process(
        pid=0,
        program=program,
        unit_module=unit_module,
        host_interface=procnode.host._interface,
        inputs={"x": 1, "theta": 3.14, "name": "alice"},
    )
    procnode.add_process(process)

    host_processor.initialize(process)
    host_mem = process.prog_memory.host_mem
    assert host_mem.read("x") == 1
    assert host_mem.read("theta") == 3.14
    assert host_mem.read("name") == "alice"

    request = NetstackCreateRequest(
        remote_id=1,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=1.0,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )

    netsquid_run(host_processor.assign(process, instr_idx=0))
    netsquid_run(qnos_processor.assign(process, "subrt1", 0))

    process.shared_mem.init_new_array(0, SER_RESPONSE_KEEP_LEN * 1)
    netsquid_run(netstack_processor.assign(process, request))

    assert process.host_mem.read("x") == 3
    assert process.shared_mem.get_reg_value("R5") == 42
    assert procnode.memmgr.phys_id_for(pid=process.pid, virt_id=0) == 0


def test_2():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)
    local_env = LocalEnvironment(global_env, global_env.get_node_id("alice"))
    procnode = create_procnode("alice", global_env, num_qubits)
    procnode.qdevice = MockQDevice(topology)

    # procnode.host.interface = MockHostInterface()

    # mock_result = ResCreateAndKeep(bell_state=BellIndex.B01)
    # procnode.netstack.interface = MockNetstackInterface(
    #     local_env, procnode.qdevice, procnode.memmgr, mock_result
    # )

    host_processor = procnode.host.processor
    qnos_processor = procnode.qnos.processor
    netstack_processor = procnode.netstack.processor

    unit_module = UnitModule.default_generic(num_qubits)

    instrs = [RunSubroutineOp(None, IqoalaVector([]), "subrt1")]
    subroutines = parse_iqoala_subroutines(
        """
SUBROUTINE subrt1
    params: 
    returns: R5 -> result
  NETQASM_START
    set R5 42
    ret_reg R5
  NETQASM_END
    """
    )

    program = create_program(instrs=instrs, subroutines=subroutines)
    process = create_process(
        pid=0,
        program=program,
        unit_module=unit_module,
        host_interface=procnode.host._interface,
        inputs={"x": 1, "theta": 3.14, "name": "alice"},
    )
    procnode.add_process(process)

    host_processor.initialize(process)

    request = NetstackCreateRequest(
        remote_id=1,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=1.0,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )

    def qnos_run() -> Generator[EventExpression, None, None]:
        yield from qnos_processor.assign(process, "subrt1", 0)
        # Mock sending signal back to Host that subroutine has finished.
        qnos_processor._interface.send_host_msg(Message(None))

    netsquid_run(host_processor.assign(process, instr_idx=0))
    netsquid_run(qnos_processor.assign(process, "subrt1", 0))
    host_processor.copy_subroutine_results(process, "subrt1")

    assert process.host_mem.read("result") == 42
    assert process.shared_mem.get_reg_value("R5") == 42


def test_2_async():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)
    local_env = LocalEnvironment(global_env, global_env.get_node_id("alice"))
    procnode = create_procnode("alice", global_env, num_qubits, asynchronous=True)
    procnode.qdevice = MockQDevice(topology)

    # procnode.host.interface = MockHostInterface()

    # mock_result = ResCreateAndKeep(bell_state=BellIndex.B01)
    # procnode.netstack.interface = MockNetstackInterface(
    #     local_env, procnode.qdevice, procnode.memmgr, mock_result
    # )

    host_processor = procnode.host.processor
    qnos_processor = procnode.qnos.processor
    netstack_processor = procnode.netstack.processor

    unit_module = UnitModule.default_generic(num_qubits)

    instrs = [RunSubroutineOp(None, IqoalaVector([]), "subrt1")]
    subroutines = parse_iqoala_subroutines(
        """
SUBROUTINE subrt1
    params: 
    returns: R5 -> result
  NETQASM_START
    set R5 42
    ret_reg R5
  NETQASM_END
    """
    )

    program = create_program(instrs=instrs, subroutines=subroutines)
    process = create_process(
        pid=0,
        program=program,
        unit_module=unit_module,
        host_interface=procnode.host._interface,
        inputs={"x": 1, "theta": 3.14, "name": "alice"},
    )
    procnode.add_process(process)

    host_processor.initialize(process)

    request = NetstackCreateRequest(
        remote_id=1,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=1.0,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )

    def host_run() -> Generator[EventExpression, None, None]:
        yield from host_processor.assign(process, instr_idx=0)

    def qnos_run() -> Generator[EventExpression, None, None]:
        yield from qnos_processor.assign(process, "subrt1", 0)
        # Mock sending signal back to Host that subroutine has finished.
        qnos_processor._interface.send_host_msg(Message(None))

    procnode.host.run = host_run
    procnode.qnos.run = qnos_run
    procnode.start()
    ns.sim_run()

    assert process.host_mem.read("result") == 42
    assert process.shared_mem.get_reg_value("R5") == 42


def test_classical_comm():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)
    alice_id = global_env.get_node_id("alice")
    bob_id = global_env.get_node_id("bob")

    class TestProcNode(ProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            process = self.memmgr.get_process(0)
            yield from self.host.processor.assign(process, 0)

    alice_procnode = create_procnode(
        "alice", global_env, num_qubits, procnode_cls=TestProcNode
    )
    bob_procnode = create_procnode(
        "bob", global_env, num_qubits, procnode_cls=TestProcNode
    )

    alice_host_processor = alice_procnode.host.processor
    bob_host_processor = bob_procnode.host.processor

    unit_module = UnitModule.default_generic(num_qubits)

    alice_instrs = [SendCMsgOp("csocket_id", "message")]
    alice_meta = ProgramMeta(
        name="alice",
        parameters=["csocket_id", "message"],
        csockets={0: "bob"},
        epr_sockets={},
    )
    alice_program = create_program(instrs=alice_instrs, meta=alice_meta)
    alice_process = create_process(
        pid=0,
        program=alice_program,
        unit_module=unit_module,
        host_interface=alice_procnode.host._interface,
        inputs={"csocket_id": 0, "message": 1337},
    )
    alice_procnode.add_process(alice_process)
    alice_host_processor.initialize(alice_process)

    bob_instrs = [ReceiveCMsgOp("csocket_id", "result")]
    bob_meta = ProgramMeta(
        name="bob", parameters=["csocket_id"], csockets={0: "alice"}, epr_sockets={}
    )
    bob_program = create_program(instrs=bob_instrs, meta=bob_meta)
    bob_process = create_process(
        pid=0,
        program=bob_program,
        unit_module=unit_module,
        host_interface=bob_procnode.host._interface,
        inputs={"csocket_id": 0},
    )
    bob_procnode.add_process(bob_process)
    bob_host_processor.initialize(bob_process)

    alice_procnode.connect_to(bob_procnode)

    # First start Bob, since Alice won't yield on anything (she only does a Send
    # instruction) and therefore calling 'start()' on alice completes her whole
    # protocol while Bob's interface has not even been started.
    bob_procnode.start()
    alice_procnode.start()
    ns.sim_run()

    assert bob_process.host_mem.read("result") == 1337


def test_classical_comm_three_nodes():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)

    class SenderProcNode(ProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            process = self.memmgr.get_process(0)
            yield from self.host.processor.assign(process, 0)

    class ReceiverProcNode(ProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            process = self.memmgr.get_process(0)
            yield from self.host.processor.assign(process, 0)
            yield from self.host.processor.assign(process, 1)

    alice_procnode = create_procnode(
        "alice", global_env, num_qubits, procnode_cls=SenderProcNode
    )
    bob_procnode = create_procnode(
        "bob", global_env, num_qubits, procnode_cls=SenderProcNode
    )
    charlie_procnode = create_procnode(
        "charlie", global_env, num_qubits, procnode_cls=ReceiverProcNode
    )

    alice_host_processor = alice_procnode.host.processor
    bob_host_processor = bob_procnode.host.processor
    charlie_host_processor = charlie_procnode.host.processor

    unit_module = UnitModule.default_generic(num_qubits)

    alice_instrs = [SendCMsgOp("csocket_id", "message")]
    alice_meta = ProgramMeta(
        name="alice",
        parameters=["csocket_id", "message"],
        csockets={0: "charlie"},
        epr_sockets={},
    )
    alice_program = create_program(instrs=alice_instrs, meta=alice_meta)
    alice_process = create_process(
        pid=0,
        program=alice_program,
        unit_module=unit_module,
        host_interface=alice_procnode.host._interface,
        inputs={"csocket_id": 0, "message": 1337},
    )
    alice_procnode.add_process(alice_process)
    alice_host_processor.initialize(alice_process)

    bob_instrs = [SendCMsgOp("csocket_id", "message")]
    bob_meta = ProgramMeta(
        name="bob",
        parameters=["csocket_id", "message"],
        csockets={0: "charlie"},
        epr_sockets={},
    )
    bob_program = create_program(instrs=bob_instrs, meta=bob_meta)
    bob_process = create_process(
        pid=0,
        program=bob_program,
        unit_module=unit_module,
        host_interface=bob_procnode.host._interface,
        inputs={"csocket_id": 0, "message": 42},
    )
    bob_procnode.add_process(bob_process)
    bob_host_processor.initialize(bob_process)

    charlie_instrs = [
        ReceiveCMsgOp("csocket_id_alice", "result_alice"),
        ReceiveCMsgOp("csocket_id_bob", "result_bob"),
    ]
    charlie_meta = ProgramMeta(
        name="bob",
        parameters=["csocket_id_alice", "csocket_id_bob"],
        csockets={0: "alice", 1: "bob"},
        epr_sockets={},
    )
    charlie_program = create_program(instrs=charlie_instrs, meta=charlie_meta)
    charlie_process = create_process(
        pid=0,
        program=charlie_program,
        unit_module=unit_module,
        host_interface=charlie_procnode.host._interface,
        inputs={"csocket_id_alice": 0, "csocket_id_bob": 1},
    )
    charlie_procnode.add_process(charlie_process)
    charlie_host_processor.initialize(charlie_process)

    alice_procnode.connect_to(charlie_procnode)
    bob_procnode.connect_to(charlie_procnode)

    # First start Charlie, since Alice and Bob don't yield on anything.
    charlie_procnode.start()
    alice_procnode.start()
    bob_procnode.start()
    ns.sim_run()

    assert charlie_process.host_mem.read("result_alice") == 1337
    assert charlie_process.host_mem.read("result_bob") == 42


def test_epr():
    num_qubits = 3
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})

    global_env = create_global_env(num_qubits)
    alice_id = global_env.get_node_id("alice")
    bob_id = global_env.get_node_id("bob")

    class TestProcNode(ProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            process = self.memmgr.get_process(0)
            request = process.prog_memory.requests[0]
            yield from self.netstack.processor.assign(process, request)

    alice_procnode = create_procnode(
        "alice", global_env, num_qubits, procnode_cls=TestProcNode
    )
    bob_procnode = create_procnode(
        "bob", global_env, num_qubits, procnode_cls=TestProcNode
    )

    alice_host_processor = alice_procnode.host.processor
    bob_host_processor = bob_procnode.host.processor

    unit_module = UnitModule.default_generic(num_qubits)

    alice_instrs = [SendCMsgOp("csocket_id", "message")]
    alice_meta = ProgramMeta(
        name="alice",
        parameters=["csocket_id", "message"],
        csockets={0: "bob"},
        epr_sockets={},
    )
    alice_program = create_program(instrs=alice_instrs, meta=alice_meta)
    alice_process = create_process(
        pid=0,
        program=alice_program,
        unit_module=unit_module,
        host_interface=alice_procnode.host._interface,
        inputs={"csocket_id": 0, "message": 1337},
    )
    alice_procnode.add_process(alice_process)
    alice_host_processor.initialize(alice_process)

    bob_instrs = [ReceiveCMsgOp("csocket_id", "result")]
    bob_meta = ProgramMeta(
        name="bob", parameters=["csocket_id"], csockets={0: "alice"}, epr_sockets={}
    )
    bob_program = create_program(instrs=bob_instrs, meta=bob_meta)
    bob_process = create_process(
        pid=0,
        program=bob_program,
        unit_module=unit_module,
        host_interface=bob_procnode.host._interface,
        inputs={"csocket_id": 0},
    )
    bob_procnode.add_process(bob_process)
    bob_host_processor.initialize(bob_process)

    alice_procnode.connect_to(bob_procnode)

    alice_request = NetstackCreateRequest(
        remote_id=bob_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=1.0,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )

    bob_request = NetstackReceiveRequest(
        remote_id=alice_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=1.0,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )

    alice_egp, bob_egp = create_egp_protocols(alice_procnode.node, bob_procnode.node)
    alice_procnode.egpmgr.add_egp(bob_id, alice_egp)
    bob_procnode.egpmgr.add_egp(alice_id, bob_egp)
    alice_process.prog_memory.requests = [alice_request]
    bob_process.prog_memory.requests = [bob_request]

    # First start Bob, since Alice won't yield on anything (she only does a Send
    # instruction) and therefore calling 'start()' on alice completes her whole
    # protocol while Bob's interface has not even been started.
    bob_procnode.start()
    alice_procnode.start()
    ns.sim_run()

    assert alice_procnode.memmgr.phys_id_for(pid=0, virt_id=0) == 0
    assert bob_procnode.memmgr.phys_id_for(pid=0, virt_id=0) == 0

    alice_qubit = alice_procnode.qdevice.get_local_qubit(0)
    bob_qubit = bob_procnode.qdevice.get_local_qubit(0)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)


if __name__ == "__main__":
    # test_initialize()
    # test_2()
    # test_2_async()
    # test_classical_comm()
    # test_classical_comm_three_nodes()
    test_epr()
