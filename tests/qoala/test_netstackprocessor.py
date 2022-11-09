from typing import Generator, Optional

from qlink_interface import (
    ReqCreateAndKeep,
    ReqCreateBase,
    ReqMeasureDirectly,
    ReqRemoteStatePrep,
    ResCreateAndKeep,
)

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import IqoalaProgram, ProgramMeta
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, Topology, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import PhysicalQuantumMemory, QDevice
from squidasm.qoala.sim.requests import EprCreateType, NetstackCreateRequest
from squidasm.util.tests import netsquid_run


class MockNetstackInterface(NetstackInterface):
    def __init__(
        self, qdevice: QDevice, memmgr: MemoryManager, egpmgr: EgpManager
    ) -> None:
        self._qdevice = qdevice
        self._memmgr = memmgr
        self._egpmgr = egpmgr

    def put_request(self, remote_id: int, request: ReqCreateBase) -> None:
        pass

    def await_result_create_keep(
        self, remote_id: int
    ) -> Generator[EventExpression, None, ResCreateAndKeep]:
        return ResCreateAndKeep()
        yield  # to make this behave as a generator

    def send_qnos_msg(self, msg: Message) -> None:
        pass


class MockQDevice(QDevice):
    def __init__(self, topology: Topology) -> None:
        self._memory = PhysicalQuantumMemory(topology.comm_ids, topology.mem_ids)

    def set_mem_pos_in_use(self, id: int, in_use: bool) -> None:
        pass


# class MockEgpProtocol(EgpProtocol):
#     def __init__(self) -> None:
#         pass

#     def put(self, request: ReqCreateBase, name: Optional[str] = None) -> None:
#         pass


def create_process(pid: int) -> IqoalaProcess:
    program = IqoalaProgram(
        instructions=[], subroutines={}, meta=ProgramMeta.empty("prog")
    )
    instance = ProgramInstance(pid=pid, program=program, inputs=ProgramInput({}))
    mem = ProgramMemory(pid=pid, unit_module=UnitModule.default_generic(3))

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
    egpmgr = EgpManager()
    interface = MockNetstackInterface(qdevice, memmgr, egpmgr)
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


def test_1():
    qdevice = MockQDevice(Topology(comm_ids={0}, mem_ids={1}))
    memmgr = MemoryManager("alice", qdevice)
    egpmgr = EgpManager()
    interface = MockNetstackInterface(qdevice, memmgr, egpmgr)
    processor = NetstackProcessor(interface)

    remote_id = 1
    result_array = 0

    request = NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=0.75,
        virt_qubit_ids=[1],
        result_array_addr=result_array,
    )

    process = create_process(pid=0)
    memmgr.add_process(process)

    process.prog_memory.shared_mem.init_new_array(result_array, 10)

    netsquid_run(processor.handle_create_ck_request(process, request))

    print(memmgr.phys_id_for(process.pid, 0))


if __name__ == "__main__":
    # test_create_link_layer_create_request()
    test_1()
