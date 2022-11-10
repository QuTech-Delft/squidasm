from typing import Dict, Generator, List, Optional

import pytest
from netqasm.sdk.build_epr import (
    SER_CREATE_IDX_NUMBER,
    SER_CREATE_IDX_TYPE,
    SER_RESPONSE_KEEP_IDX_BELL_STATE,
    SER_RESPONSE_KEEP_IDX_GOODNESS,
    SER_RESPONSE_KEEP_LEN,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME,
    SER_RESPONSE_MEASURE_LEN,
)
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z
from netsquid.qubits.ketstates import BellIndex
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
from squidasm.qoala.lang.iqoala import IqoalaProgram, ProgramMeta
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.constants import PI
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, Topology, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice, QDeviceCommand
from squidasm.qoala.sim.requests import (
    EprCreateType,
    NetstackCreateRequest,
    NetstackReceiveRequest,
)
from squidasm.util.tests import netsquid_run


class MockNetstackInterface(NetstackInterface):
    def __init__(
        self,
        qdevice: QDevice,
        memmgr: MemoryManager,
        mock_result: ResCreate,
    ) -> None:
        self._qdevice = qdevice
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
        pass

    def reset(self) -> None:
        self._requests_put = {}
        self._awaited_result_ck = []
        self._awaited_mem_free_sig_count = 0


class MockQDevice(QDevice):
    def __init__(self, topology: Topology) -> None:
        self._memory = PhysicalQuantumMemory(topology.comm_ids, topology.mem_ids)

        self._executed_commands: List[QDeviceCommand] = []

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


def test_create_link_layer_create_request():
    qdevice = MockQDevice(Topology(comm_ids={0}, mem_ids={1}))
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 3
    num_pairs = 2
    fidelity = 0.75
    result_array = 5

    request_ck = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0],
        result_array_addr=result_array,
    )

    ll_request_ck = processor._create_link_layer_create_request(request_ck)

    assert ll_request_ck == ReqCreateAndKeep(
        remote_node_id=remote_id, minimum_fidelity=fidelity, number=num_pairs
    )

    request_md = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.MEASURE_DIRECTLY,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0],
        result_array_addr=result_array,
    )

    ll_request_md = processor._create_link_layer_create_request(request_md)

    assert ll_request_md == ReqMeasureDirectly(
        remote_node_id=remote_id, minimum_fidelity=fidelity, number=num_pairs
    )

    request_rsp = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.REMOTE_STATE_PREP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0],
        result_array_addr=result_array,
    )

    ll_request_rsp = processor._create_link_layer_create_request(request_rsp)

    assert ll_request_rsp == ReqRemoteStatePrep(
        remote_node_id=remote_id, minimum_fidelity=fidelity, number=num_pairs
    )


def test_create_single_pair_1():
    topology = Topology(comm_ids={0}, mem_ids={1})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )

    pid = 0
    process = create_process(pid, unit_module)
    memmgr.add_process(process)

    process.prog_memory.shared_mem.init_new_array(result_array_addr, 10)

    # At the start, nothing should be allocated yet.
    assert memmgr.phys_id_for(pid, virt_id=0) is None

    # Create a single pair (communication with link layer is mocked) for the request.
    netsquid_run(processor.create_single_pair(process, request, virt_id=0))

    # Should have allocated virt_id 0.
    assert memmgr.phys_id_for(pid, virt_id=0) == 0

    assert len(interface._requests_put[remote_id]) == 1

    # Should have put a LL request with correct params **and number of pairs = 1**.
    assert interface._requests_put[remote_id][0] == ReqCreateAndKeep(
        remote_node_id=remote_id, minimum_fidelity=fidelity, number=1
    )

    # Mock result indicated bell state B00, so no local gates should have been executed.
    assert len(qdevice._executed_commands) == 0

    with pytest.raises(AllocError):
        # AllocError since the only comm qubit has already been allocated.
        netsquid_run(processor.create_single_pair(process, request, virt_id=0))

    # Free up the communication qubit again.
    memmgr.free(pid, 0)

    interface.reset()
    qdevice.reset()

    # See the next mocked result to indicate Bell state B01.
    interface._mock_result = ResCreateAndKeep(bell_state=BellIndex.B01)

    # Create a single pair again. Try virt ID 1, which is not a comm qubit.
    with pytest.raises(AllocError):
        netsquid_run(processor.create_single_pair(process, request, virt_id=1))

    # Try with virt ID = 0 again.
    netsquid_run(processor.create_single_pair(process, request, virt_id=0))

    # Should have allocated virt_id 0 again.
    assert memmgr.phys_id_for(pid, virt_id=0) == 0

    assert len(interface._requests_put[remote_id]) == 1

    # Should have put a LL request with correct params **and number of pairs = 1**.
    assert interface._requests_put[remote_id][0] == ReqCreateAndKeep(
        remote_node_id=remote_id, minimum_fidelity=fidelity, number=1
    )

    # Mock result indicated bell state B01, so an X gate should have been executed.
    assert len(qdevice._executed_commands) == 1
    assert qdevice._executed_commands[0] == QDeviceCommand(INSTR_ROT_X, [0], angle=PI)


def test_create_single_pair_2():

    # Let HW have 3 comm qubits.
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )

    process0 = create_process(pid=0, unit_module=unit_module)
    process1 = create_process(pid=1, unit_module=unit_module)
    process2 = create_process(pid=2, unit_module=unit_module)
    memmgr.add_process(process0)
    memmgr.add_process(process1)
    memmgr.add_process(process2)
    process0.prog_memory.shared_mem.init_new_array(result_array_addr, 10)
    process1.prog_memory.shared_mem.init_new_array(result_array_addr, 10)
    process2.prog_memory.shared_mem.init_new_array(result_array_addr, 10)

    # At the start, nothing should be allocated yet.
    assert all(memmgr.phys_id_for(pid=0, virt_id=i) is None for i in range(3))
    assert all(memmgr.phys_id_for(pid=1, virt_id=i) is None for i in range(3))
    assert all(memmgr.phys_id_for(pid=2, virt_id=i) is None for i in range(3))

    # We are use the same request object for all 3 processes.

    # Create a single pair for process 0, based on the request object.
    # Store the result in virt qubit 0.
    netsquid_run(processor.create_single_pair(process0, request, virt_id=0))

    # Should have allocated virt_id 0 for process 0.
    assert memmgr.phys_id_for(pid=0, virt_id=0) == 0
    assert len(interface._requests_put[remote_id]) == 1

    # Create another pair for process 0.
    with pytest.raises(AllocError):
        # Using virt ID 0 again should raise an AllocError.
        netsquid_run(processor.create_single_pair(process0, request, virt_id=0))
    # Use virt ID 1.
    netsquid_run(processor.create_single_pair(process0, request, virt_id=1))

    # Should have allocated virt_id 1 for process 0.
    assert memmgr.phys_id_for(pid=0, virt_id=1) == 1

    # Create a single pair for process 1, using virt ID 0.
    # Should get mapped to phys ID 2 (since 0 and 1 already in use).
    netsquid_run(processor.create_single_pair(process1, request, virt_id=0))
    assert memmgr.phys_id_for(pid=1, virt_id=0) == 2

    # Create a single pair for process 1, using virt ID 1.
    # Should give an AllocError since no physical comm qubits are available.
    with pytest.raises(AllocError):
        netsquid_run(processor.create_single_pair(process1, request, virt_id=1))

    # Create a single pair for process 2, using virt ID 0.
    # Should give an AllocError since no physical comm qubits are available.
    with pytest.raises(AllocError):
        netsquid_run(processor.create_single_pair(process2, request, virt_id=0))


def test_write_pair_result():
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    process = create_process(0, unit_module)
    memmgr.add_process(process)

    # Only goodness and bell state should be written to the NetQASM array.
    goodness = 27
    bell_state = 3
    ll_result = ResCreateAndKeep(goodness=goodness, bell_state=bell_state)
    pair_index = 5
    result_array_addr = 0
    duration = 7600.0

    # Make sure the result array is initialized with enough entries.
    # Need at least SER_RESPONSE_KEEP_LEN * num_pairs entries.
    shared_mem = process.prog_memory.shared_mem
    shared_mem.init_new_array(result_array_addr, SER_RESPONSE_KEEP_LEN * 10)

    processor.write_pair_result(
        process, ll_result, pair_index, result_array_addr, duration
    )

    # 'goodness' entry is used for rounded duration in us
    expected_duration = int(duration / 1000)

    assert (
        shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * pair_index + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        == expected_duration
    )

    assert (
        shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * pair_index + SER_RESPONSE_KEEP_IDX_BELL_STATE,
        )
        == bell_state
    )


def test_handle_create_ck_request():
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0, 1, 2],
        result_array_addr=result_array_addr,
    )

    process = create_process(0, unit_module)
    memmgr.add_process(process)
    shared_mem = process.prog_memory.shared_mem
    shared_mem.init_new_array(result_array_addr, SER_RESPONSE_KEEP_LEN * num_pairs)

    netsquid_run(processor.handle_create_ck_request(process, request))
    assert memmgr.phys_id_for(pid=0, virt_id=0) == 0
    assert memmgr.phys_id_for(pid=0, virt_id=1) == 1
    assert memmgr.phys_id_for(pid=0, virt_id=2) == 2


def test_handle_create_ck_request_invalid_virt_ids():
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0, 0, 0],
        result_array_addr=result_array_addr,
    )

    process = create_process(0, unit_module)
    memmgr.add_process(process)
    shared_mem = process.prog_memory.shared_mem
    shared_mem.init_new_array(result_array_addr, SER_RESPONSE_KEEP_LEN * num_pairs)

    with pytest.raises(AllocError):
        # After the first pair has been generated, virt ID 0 has been allocated,
        # so the next pair should not be able to allocate virt ID 0 again.
        netsquid_run(processor.handle_create_ck_request(process, request))


def test_receive_single_pair_1():
    topology = Topology(comm_ids={0}, mem_ids={1})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackReceiveRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )

    pid = 0
    process = create_process(pid, unit_module)
    memmgr.add_process(process)

    process.prog_memory.shared_mem.init_new_array(result_array_addr, 10)

    # At the start, nothing should be allocated yet.
    assert memmgr.phys_id_for(pid, virt_id=0) is None

    # Create a single pair (communication with link layer is mocked) for the request.
    netsquid_run(processor.receive_single_pair(process, request, virt_id=0))

    # Should have allocated virt_id 0.
    assert memmgr.phys_id_for(pid, virt_id=0) == 0

    assert len(interface._requests_put[remote_id]) == 1

    # Should have put a LL request with correct params **and number of pairs = 1**.
    assert interface._requests_put[remote_id][0] == ReqReceive(remote_node_id=remote_id)

    # No local gates should have been executed.
    assert len(qdevice._executed_commands) == 0

    with pytest.raises(AllocError):
        # AllocError since the only comm qubit has already been allocated.
        netsquid_run(processor.receive_single_pair(process, request, virt_id=0))

    # Free up the communication qubit again.
    memmgr.free(pid, 0)

    interface.reset()
    qdevice.reset()

    # See the next mocked result to indicate Bell state B01.
    interface._mock_result = ResCreateAndKeep(bell_state=BellIndex.B01)

    # Create a single pair again. Try virt ID 1, which is not a comm qubit.
    with pytest.raises(AllocError):
        netsquid_run(processor.receive_single_pair(process, request, virt_id=1))

    # Try with virt ID = 0 again.
    netsquid_run(processor.receive_single_pair(process, request, virt_id=0))

    # Should have allocated virt_id 0 again.
    assert memmgr.phys_id_for(pid, virt_id=0) == 0

    assert len(interface._requests_put[remote_id]) == 1

    # Should have put a LL request with correct params **and number of pairs = 1**.
    assert interface._requests_put[remote_id][0] == ReqReceive(remote_node_id=remote_id)

    # Still no local gates should have been executed.
    assert len(qdevice._executed_commands) == 0


def test_receive_single_pair_2():

    # Let HW have 3 comm qubits.
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackReceiveRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )

    process0 = create_process(pid=0, unit_module=unit_module)
    process1 = create_process(pid=1, unit_module=unit_module)
    process2 = create_process(pid=2, unit_module=unit_module)
    memmgr.add_process(process0)
    memmgr.add_process(process1)
    memmgr.add_process(process2)
    process0.prog_memory.shared_mem.init_new_array(result_array_addr, 10)
    process1.prog_memory.shared_mem.init_new_array(result_array_addr, 10)
    process2.prog_memory.shared_mem.init_new_array(result_array_addr, 10)

    # At the start, nothing should be allocated yet.
    assert all(memmgr.phys_id_for(pid=0, virt_id=i) is None for i in range(3))
    assert all(memmgr.phys_id_for(pid=1, virt_id=i) is None for i in range(3))
    assert all(memmgr.phys_id_for(pid=2, virt_id=i) is None for i in range(3))

    # We are use the same request object for all 3 processes.

    # Create a single pair for process 0, based on the request object.
    # Store the result in virt qubit 0.
    netsquid_run(processor.receive_single_pair(process0, request, virt_id=0))

    # Should have allocated virt_id 0 for process 0.
    assert memmgr.phys_id_for(pid=0, virt_id=0) == 0
    assert len(interface._requests_put[remote_id]) == 1

    # Create another pair for process 0.
    with pytest.raises(AllocError):
        # Using virt ID 0 again should raise an AllocError.
        netsquid_run(processor.receive_single_pair(process0, request, virt_id=0))
    # Use virt ID 1.
    netsquid_run(processor.receive_single_pair(process0, request, virt_id=1))

    # Should have allocated virt_id 1 for process 0.
    assert memmgr.phys_id_for(pid=0, virt_id=1) == 1

    # Create a single pair for process 1, using virt ID 0.
    # Should get mapped to phys ID 2 (since 0 and 1 already in use).
    netsquid_run(processor.receive_single_pair(process1, request, virt_id=0))
    assert memmgr.phys_id_for(pid=1, virt_id=0) == 2

    # Create a single pair for process 1, using virt ID 1.
    # Should give an AllocError since no physical comm qubits are available.
    with pytest.raises(AllocError):
        netsquid_run(processor.receive_single_pair(process1, request, virt_id=1))

    # Create a single pair for process 2, using virt ID 0.
    # Should give an AllocError since no physical comm qubits are available.
    with pytest.raises(AllocError):
        netsquid_run(processor.receive_single_pair(process2, request, virt_id=0))


def test_handle_receive_ck_request():
    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    qdevice = MockQDevice(topology)
    unit_module = UnitModule.from_topology(topology)
    memmgr = MemoryManager("alice", qdevice)
    mock_result = ResCreateAndKeep(bell_state=BellIndex.B00)
    interface = MockNetstackInterface(qdevice, memmgr, mock_result)
    processor = NetstackProcessor(interface)

    remote_id = 1
    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    request = NetstackReceiveRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0, 1, 2],
        result_array_addr=result_array_addr,
    )

    process = create_process(0, unit_module)
    memmgr.add_process(process)
    shared_mem = process.prog_memory.shared_mem
    shared_mem.init_new_array(result_array_addr, SER_RESPONSE_KEEP_LEN * num_pairs)

    netsquid_run(processor.handle_receive_ck_request(process, request))
    assert memmgr.phys_id_for(pid=0, virt_id=0) == 0
    assert memmgr.phys_id_for(pid=0, virt_id=1) == 1
    assert memmgr.phys_id_for(pid=0, virt_id=2) == 2


if __name__ == "__main__":
    test_create_link_layer_create_request()
    test_create_single_pair_1()
    test_create_single_pair_2()
    test_write_pair_result()
    test_handle_create_ck_request()
    test_handle_create_ck_request_invalid_virt_ids()
    test_receive_single_pair_1()
    test_receive_single_pair_2()
    test_handle_receive_ck_request()
