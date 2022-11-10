from __future__ import annotations

from typing import Dict, Generator, List, Optional, Tuple

import netsquid as ns
import pytest
from netqasm.lang.parsing import parse_text_subroutine
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
from squidasm.qoala.lang.iqoala import IqoalaProgram, IqoalaSubroutine, ProgramMeta
from squidasm.qoala.runtime.config import GenericQDeviceConfig
from squidasm.qoala.runtime.environment import (
    GlobalEnvironment,
    GlobalNodeInfo,
    LocalEnvironment,
)
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.sim.build import build_generic_qprocessor
from squidasm.qoala.sim.constants import PI
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager, NotAllocatedError
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, Topology, UnitModule
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackcomp import NetstackComponent
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.netstackprocessor import NetstackProcessor
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import (
    GenericPhysicalQuantumMemory,
    PhysicalQuantumMemory,
    QDevice,
    QDeviceCommand,
    QDeviceType,
)
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.qnosprocessor import GenericProcessor, QnosProcessor
from squidasm.qoala.sim.requests import (
    EprCreateType,
    NetstackCreateRequest,
    NetstackReceiveRequest,
)
from squidasm.util.tests import has_multi_state, has_state, netsquid_run


def perfect_generic_qdevice(node_name: str, num_qubits: int) -> QDevice:
    cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    processor = build_generic_qprocessor(name="processor", cfg=cfg)
    node = Node(name=node_name, qmemory=processor)
    return QDevice(
        node=node,
        typ=QDeviceType.GENERIC,
        memory=GenericPhysicalQuantumMemory(num_qubits),
    )


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


def setup_components_generic(
    num_qubits: int,
) -> Tuple[NetstackProcessor, NetstackProcessor]:
    # TODO: SUPPORT ANY TOPOLOGY (ALSO REQUIRES REFACTORING CONFIG HANDLING)
    alice_qdevice = perfect_generic_qdevice("alice", num_qubits)
    bob_qdevice = perfect_generic_qdevice("bob", num_qubits)

    alice_node = alice_qdevice._node
    bob_node = bob_qdevice._node

    env = GlobalEnvironment()
    env.add_node(
        alice_node.ID, GlobalNodeInfo.default_nv(alice_node.name, alice_node.ID, 2)
    )
    env.add_node(bob_node.ID, GlobalNodeInfo.default_nv(bob_node.name, bob_node.ID, 2))

    alice_comp = NetstackComponent(node=alice_node, global_env=env)
    bob_comp = NetstackComponent(node=bob_node, global_env=env)

    alice_comp.peer_out_port("bob").connect(bob_comp.peer_in_port("alice"))
    alice_comp.peer_in_port("bob").connect(bob_comp.peer_out_port("alice"))

    alice_memmgr = MemoryManager(alice_node.name, alice_qdevice)
    bob_memmgr = MemoryManager(bob_node.name, bob_qdevice)

    alice_egpmgr = EgpManager()
    bob_egpmgr = EgpManager()

    alice_intf = NetstackInterface(
        alice_comp,
        LocalEnvironment(env, alice_node.ID),
        alice_qdevice,
        alice_memmgr,
        alice_egpmgr,
    )
    bob_intf = NetstackInterface(
        bob_comp,
        LocalEnvironment(env, bob_node.ID),
        bob_qdevice,
        bob_memmgr,
        bob_egpmgr,
    )

    alice_processor = NetstackProcessor(alice_intf)
    bob_processor = NetstackProcessor(bob_intf)

    return (alice_processor, bob_processor)


def create_egp_protocols(node1: Node, node2: Node) -> Tuple[EgpProtocol, EgpProtocol]:
    link_dist = PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=1000.0)
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[node1, node2],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    return EgpProtocol(node1, link_prot), EgpProtocol(node2, link_prot)


def create_netstack_create_request(remote_id: int) -> NetstackCreateRequest:
    return NetstackCreateRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=0.75,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )


def create_netstack_receive_request(remote_id: int) -> NetstackReceiveRequest:
    return NetstackReceiveRequest(
        remote_id=remote_id,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=1,
        fidelity=0.75,
        virt_qubit_ids=[0],
        result_array_addr=0,
    )


def test_1():
    alice_processor, bob_processor = setup_components_generic(num_qubits=2)

    topology = Topology(comm_ids={0}, mem_ids={1})
    unit_module = UnitModule.from_topology(topology)

    alice_node = alice_processor._interface._comp.node
    bob_node = bob_processor._interface._comp.node

    num_pairs = 3
    fidelity = 0.75
    result_array_addr = 0

    alice_request = NetstackCreateRequest(
        remote_id=bob_node.ID,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )
    bob_request = NetstackReceiveRequest(
        remote_id=alice_node.ID,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[1],
        result_array_addr=result_array_addr,
    )

    alice_memmgr = alice_processor._interface.memmgr
    bob_memmgr = bob_processor._interface.memmgr

    alice_egpmgr = alice_processor._interface.egpmgr
    bob_egpmgr = bob_processor._interface.egpmgr

    alice_egp, bob_egp = create_egp_protocols(alice_node, bob_node)
    alice_egpmgr.add_egp(bob_node.ID, alice_egp)
    bob_egpmgr.add_egp(alice_node.ID, bob_egp)

    class NetstackProcessorProtocol(Protocol):
        def __init__(self, name: str, processor: NetstackProcessor) -> None:
            super().__init__(name)
            self._processor = processor
            self._memmgr = processor._interface.memmgr
            self._pid = 0
            self._process = create_process(self._pid, unit_module)
            self._memmgr.add_process(self._process)

        @property
        def pid(self) -> int:
            return self._pid

        @property
        def memmgr(self) -> MemoryManager:
            return self._memmgr

    class AliceProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            yield from self._processor._interface.receive_peer_msg("bob")
            yield from self._processor.create_single_pair(
                self._process, alice_request, virt_id=0
            )

    class BobProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            self._processor._interface.send_peer_msg("alice", Message("ready"))
            yield from self._processor.receive_single_pair(
                self._process, bob_request, virt_id=0
            )

    alice = AliceProtocol("alice", alice_processor)
    alice_processor._interface.start()  # also starts peer listeners
    alice.start()
    alice_egp.start()

    bob = BobProtocol("bob", bob_processor)
    bob_processor._interface.start()  # also starts peer listeners
    bob.start()
    bob_egp.start()

    link_prot = alice_egp._ll_prot  # same as bob_egp._ll_prot
    link_prot.start()

    ns.sim_run()

    assert alice.memmgr.phys_id_for(alice.pid, 0) == 0
    assert bob.memmgr.phys_id_for(bob.pid, 0) == 0


def test_2():
    alice_processor, bob_processor = setup_components_generic(num_qubits=2)

    topology = Topology(comm_ids={0}, mem_ids={1})
    unit_module = UnitModule.from_topology(topology)

    alice_node = alice_processor._interface._comp.node
    bob_node = bob_processor._interface._comp.node

    num_pairs = 1
    fidelity = 0.75
    result_array_addr = 0

    alice_request = NetstackCreateRequest(
        remote_id=bob_node.ID,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0],
        result_array_addr=result_array_addr,
    )
    bob_request = NetstackReceiveRequest(
        remote_id=alice_node.ID,
        epr_socket_id=0,
        typ=EprCreateType.CREATE_KEEP,
        num_pairs=num_pairs,
        fidelity=fidelity,
        virt_qubit_ids=[0],
        result_array_addr=result_array_addr,
    )

    alice_memmgr = alice_processor._interface.memmgr
    bob_memmgr = bob_processor._interface.memmgr

    alice_egpmgr = alice_processor._interface.egpmgr
    bob_egpmgr = bob_processor._interface.egpmgr

    alice_egp, bob_egp = create_egp_protocols(alice_node, bob_node)
    alice_egpmgr.add_egp(bob_node.ID, alice_egp)
    bob_egpmgr.add_egp(alice_node.ID, bob_egp)

    class NetstackProcessorProtocol(Protocol):
        def __init__(self, name: str, processor: NetstackProcessor) -> None:
            super().__init__(name)
            self._processor = processor
            self._memmgr = processor._interface.memmgr
            self._pid = 0
            self._process = create_process(self._pid, unit_module)
            self._memmgr.add_process(self._process)
            self._process.prog_memory.shared_mem.init_new_array(result_array_addr, 10)

        @property
        def pid(self) -> int:
            return self._pid

        @property
        def process(self) -> IqoalaProcess:
            return self._process

        @property
        def memmgr(self) -> MemoryManager:
            return self._memmgr

        @property
        def shared_mem(self) -> SharedMemory:
            return self.process.prog_memory.shared_mem

    class AliceProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            yield from self._processor._interface.receive_peer_msg("bob")
            yield from self._processor.handle_create_ck_request(
                self._process, alice_request
            )

    class BobProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            self._processor._interface.send_peer_msg("alice", Message("ready"))
            yield from self._processor.handle_receive_ck_request(
                self._process, bob_request
            )

    alice = AliceProtocol("alice", alice_processor)
    alice_processor._interface.start()  # also starts peer listeners
    alice.start()
    alice_egp.start()

    bob = BobProtocol("bob", bob_processor)
    bob_processor._interface.start()  # also starts peer listeners
    bob.start()
    bob_egp.start()

    link_prot = alice_egp._ll_prot  # same as bob_egp._ll_prot
    link_prot.start()

    assert (
        alice.shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is None
    )

    ns.sim_run()

    assert alice.memmgr.phys_id_for(alice.pid, 0) == 0
    assert bob.memmgr.phys_id_for(bob.pid, 0) == 0

    assert (
        alice.shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is not None
    )

    alice_qubit = alice_processor.qdevice.get_local_qubit(0)
    bob_qubit = bob_processor.qdevice.get_local_qubit(0)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)


def test_3():
    alice_processor, bob_processor = setup_components_generic(num_qubits=3)

    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    unit_module = UnitModule.from_topology(topology)

    alice_node = alice_processor._interface._comp.node
    bob_node = bob_processor._interface._comp.node

    result_array_addr = 0

    alice_requests = {
        0: create_netstack_create_request(remote_id=bob_node.ID),
        1: create_netstack_create_request(remote_id=bob_node.ID),
    }
    bob_requests = {
        0: create_netstack_receive_request(remote_id=alice_node.ID),
        1: create_netstack_receive_request(remote_id=alice_node.ID),
    }

    alice_memmgr = alice_processor._interface.memmgr
    bob_memmgr = bob_processor._interface.memmgr

    alice_egpmgr = alice_processor._interface.egpmgr
    bob_egpmgr = bob_processor._interface.egpmgr

    alice_egp, bob_egp = create_egp_protocols(alice_node, bob_node)
    alice_egpmgr.add_egp(bob_node.ID, alice_egp)
    bob_egpmgr.add_egp(alice_node.ID, bob_egp)

    class NetstackProcessorProtocol(Protocol):
        def __init__(
            self,
            name: str,
            processor: NetstackProcessor,
            processes: Dict[int, IqoalaProcess],
        ) -> None:
            super().__init__(name)
            self._processor = processor
            self._memmgr = processor._interface.memmgr
            self._processes = processes

        @property
        def processes(self) -> Dict[int, IqoalaProcess]:
            return self._processes

        @property
        def memmgr(self) -> MemoryManager:
            return self._memmgr

    class AliceProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            for pid, process in self.processes.items():
                yield from self._processor._interface.receive_peer_msg("bob")
                yield from self._processor.handle_create_ck_request(
                    process, alice_requests[pid]
                )

    class BobProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            for pid, process in self.processes.items():
                self._processor._interface.send_peer_msg("alice", Message("ready"))
                yield from self._processor.handle_receive_ck_request(
                    process, bob_requests[pid]
                )

    alice_process0 = create_process(pid=0, unit_module=unit_module)
    alice_process1 = create_process(pid=1, unit_module=unit_module)
    alice_process0.shared_mem.init_new_array(0, 10)
    alice_process1.shared_mem.init_new_array(0, 10)
    alice_memmgr.add_process(alice_process0)
    alice_memmgr.add_process(alice_process1)
    alice = AliceProtocol(
        "alice", alice_processor, {0: alice_process0, 1: alice_process1}
    )
    alice_processor._interface.start()  # also starts peer listeners
    alice.start()
    alice_egp.start()

    bob_process0 = create_process(pid=0, unit_module=unit_module)
    bob_process1 = create_process(pid=1, unit_module=unit_module)
    bob_process0.shared_mem.init_new_array(0, 10)
    bob_process1.shared_mem.init_new_array(0, 10)
    bob_memmgr.add_process(bob_process0)
    bob_memmgr.add_process(bob_process1)
    bob = BobProtocol("bob", bob_processor, {0: bob_process0, 1: bob_process1})
    bob_processor._interface.start()  # also starts peer listeners
    bob.start()
    bob_egp.start()

    link_prot = alice_egp._ll_prot  # same as bob_egp._ll_prot
    link_prot.start()

    assert (
        alice.processes[0].shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is None
    )

    ns.sim_run()

    assert alice.memmgr.phys_id_for(alice.processes[0].pid, 0) == 0
    assert alice.memmgr.phys_id_for(alice.processes[1].pid, 0) == 1
    assert bob.memmgr.phys_id_for(bob.processes[0].pid, 0) == 0
    assert bob.memmgr.phys_id_for(bob.processes[1].pid, 0) == 1

    assert (
        alice.processes[0].shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is not None
    )

    alice_qubit = alice_processor.qdevice.get_local_qubit(0)
    bob_qubit = bob_processor.qdevice.get_local_qubit(0)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)

    alice_qubit = alice_processor.qdevice.get_local_qubit(1)
    bob_qubit = bob_processor.qdevice.get_local_qubit(1)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)

    alice_qubit = alice_processor.qdevice.get_local_qubit(2)
    assert alice_qubit is None
    bob_qubit = bob_processor.qdevice.get_local_qubit(2)
    assert bob_qubit is None


def test_4():
    alice_processor, bob_processor = setup_components_generic(num_qubits=3)

    topology = Topology(comm_ids={0, 1, 2}, mem_ids={0, 1, 2})
    unit_module = UnitModule.from_topology(topology)

    alice_node = alice_processor._interface._comp.node
    bob_node = bob_processor._interface._comp.node

    result_array_addr = 0

    alice_requests = {
        0: create_netstack_create_request(remote_id=bob_node.ID),
        1: create_netstack_create_request(remote_id=bob_node.ID),
    }
    bob_requests = {
        0: create_netstack_receive_request(remote_id=alice_node.ID),
        1: create_netstack_receive_request(remote_id=alice_node.ID),
    }

    alice_memmgr = alice_processor._interface.memmgr
    bob_memmgr = bob_processor._interface.memmgr

    alice_egpmgr = alice_processor._interface.egpmgr
    bob_egpmgr = bob_processor._interface.egpmgr

    alice_egp, bob_egp = create_egp_protocols(alice_node, bob_node)
    alice_egpmgr.add_egp(bob_node.ID, alice_egp)
    bob_egpmgr.add_egp(alice_node.ID, bob_egp)

    class NetstackProcessorProtocol(Protocol):
        def __init__(
            self,
            name: str,
            processor: NetstackProcessor,
            processes: Dict[int, IqoalaProcess],
        ) -> None:
            super().__init__(name)
            self._processor = processor
            self._memmgr = processor._interface.memmgr
            self._processes = processes

        @property
        def processes(self) -> Dict[int, IqoalaProcess]:
            return self._processes

        @property
        def memmgr(self) -> MemoryManager:
            return self._memmgr

    class AliceProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            for pid, process in self.processes.items():
                yield from self._processor.handle_create_request(
                    process, alice_requests[pid]
                )

    class BobProtocol(NetstackProcessorProtocol):
        def run(self) -> Generator[EventExpression, None, None]:
            for pid, process in self.processes.items():
                yield from self._processor.handle_receive_request(
                    process, bob_requests[pid]
                )

    alice_process0 = create_process(pid=0, unit_module=unit_module)
    alice_process1 = create_process(pid=1, unit_module=unit_module)
    alice_process0.shared_mem.init_new_array(0, 10)
    alice_process1.shared_mem.init_new_array(0, 10)
    alice_memmgr.add_process(alice_process0)
    alice_memmgr.add_process(alice_process1)
    alice = AliceProtocol(
        "alice", alice_processor, {0: alice_process0, 1: alice_process1}
    )
    alice_processor._interface.start()  # also starts peer listeners
    alice.start()
    alice_egp.start()

    bob_process0 = create_process(pid=0, unit_module=unit_module)
    bob_process1 = create_process(pid=1, unit_module=unit_module)
    bob_process0.shared_mem.init_new_array(0, 10)
    bob_process1.shared_mem.init_new_array(0, 10)
    bob_memmgr.add_process(bob_process0)
    bob_memmgr.add_process(bob_process1)
    bob = BobProtocol("bob", bob_processor, {0: bob_process0, 1: bob_process1})
    bob_processor._interface.start()  # also starts peer listeners
    bob.start()
    bob_egp.start()

    link_prot = alice_egp._ll_prot  # same as bob_egp._ll_prot
    link_prot.start()

    assert (
        alice.processes[0].shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is None
    )

    ns.sim_run()

    assert alice.memmgr.phys_id_for(alice.processes[0].pid, 0) == 0
    assert alice.memmgr.phys_id_for(alice.processes[1].pid, 0) == 1
    assert bob.memmgr.phys_id_for(bob.processes[0].pid, 0) == 0
    assert bob.memmgr.phys_id_for(bob.processes[1].pid, 0) == 1

    assert (
        alice.processes[0].shared_mem.get_array_part(
            result_array_addr,
            SER_RESPONSE_KEEP_LEN * 0 + SER_RESPONSE_KEEP_IDX_GOODNESS,
        )
        is not None
    )

    alice_qubit = alice_processor.qdevice.get_local_qubit(0)
    bob_qubit = bob_processor.qdevice.get_local_qubit(0)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)

    alice_qubit = alice_processor.qdevice.get_local_qubit(1)
    bob_qubit = bob_processor.qdevice.get_local_qubit(1)
    assert has_multi_state([alice_qubit, bob_qubit], ketstates.b00)

    alice_qubit = alice_processor.qdevice.get_local_qubit(2)
    assert alice_qubit is None
    bob_qubit = bob_processor.qdevice.get_local_qubit(2)
    assert bob_qubit is None


if __name__ == "__main__":
    test_1()
    test_2()
    test_3()
    test_4()
