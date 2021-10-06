import unittest
from typing import Dict, Generator, Optional, Type

import netsquid as ns
from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
    SubroutineMessage,
)
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.components import QuantumProcessor
from netsquid.qubits import ketstates, qubitapi
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_nv.magic_distributor import NVSingleClickMagicDistributor

from pydynaa import EventExpression
from squidasm.run.stack.build import build_nv_qdevice
from squidasm.run.stack.config import NVQDeviceConfig
from squidasm.sim.stack.common import AppMemory
from squidasm.sim.stack.host import Host
from squidasm.sim.stack.processor import NVProcessor
from squidasm.sim.stack.qnos import Qnos
from squidasm.sim.stack.stack import NodeStack


class TestTwoNodes(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        nv_cfg = NVQDeviceConfig.perfect_config()
        alice_qdevice = build_nv_qdevice("nv_qdevice_alice", cfg=nv_cfg)
        self._alice = NodeStack(
            "alice", qdevice_type="nv", qdevice=alice_qdevice, node_id=0
        )
        self._alice.host = Host(self._alice.host_comp)
        self._alice.qnos = Qnos(self._alice.qnos_comp)
        self._alice.qnos.processor = NVProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )
        # don't clear app memory so we can inspect it
        self._alice.qnos.handler.clear_memory = False

        bob_qdevice = build_nv_qdevice("nv_qdevice_bob", cfg=nv_cfg)
        self._bob = NodeStack("bob", qdevice_type="nv", qdevice=bob_qdevice, node_id=1)
        self._bob.host = Host(self._bob.host_comp)
        self._bob.qnos = Qnos(self._bob.qnos_comp)
        self._bob.qnos.processor = NVProcessor(
            self._bob.qnos_comp.processor_comp, self._bob.qnos
        )
        # don't clear app memory so we can inspect it
        self._bob.qnos.handler.clear_memory = False

        self._host_alice: Optional[Type[Host]] = None
        self._host_bob: Optional[Type[Host]] = None

        self._alice.connect_to(self._bob)

        self._link_dist = NVSingleClickMagicDistributor(
            nodes=[self._alice.node, self._bob.node],
            length_A=0.001,
            length_B=0.001,
            full_cycle=0.001,
            t_cycle=10,
        )
        self._link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[self._alice.node, self._bob.node],
            magic_distributor=self._link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )

        self._alice.assign_ll_protocol(self._link_prot)
        self._bob.assign_ll_protocol(self._link_prot)

    def tearDown(self) -> None:
        assert self._host_alice is not None
        assert self._host_bob is not None
        self._alice.host = self._host_alice(self._alice.host_comp)
        self._bob.host = self._host_bob(self._bob.host_comp)

        self._link_prot.start()
        self._alice.start()
        self._bob.start()

        ns.sim_run()
        if self._check_qmem:
            self._check_qmem(self._alice.qdevice, self._bob.qdevice)
        if self._check_cmem:
            self._check_cmem(self._alice.qnos.app_memories, self._bob.qnos.app_memories)

    def test_entangle_ck(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R0 0
        set R1 1
        set R2 20
        array R2 @0
        store R0 @0[R0]
        store R1 @0[R1]
        create_epr R1 R0 R0 R0 R0
        """

        SUBRT_2 = """
        # NETQASM 1.0
        # APPID 0
        set R0 0
        set R1 1
        set R2 20
        array R2 @0
        store R0 @0[R0]
        store R1 @0[R1]
        recv_epr R0 R0 R0 R0
        """

        class AliceHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 1)))
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("R0") == 0
                assert app_mem.get_reg_value("R1") == 1
                assert app_mem.get_reg_value("R2") == 20
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        class BobHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 0)))
                subroutine = parse_text_subroutine(SUBRT_2, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("R0") == 0
                assert app_mem.get_reg_value("R1") == 1
                assert app_mem.get_reg_value("R2") == 20
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        def check_qmem(
            qdevice_alice: QuantumProcessor, qdevice_bob: QuantumProcessor
        ) -> None:
            [q0_a] = qdevice_alice.peek(0, skip_noise=True)
            [q0_b] = qdevice_bob.peek(0, skip_noise=True)
            print(f"q0_a:\n{q0_a.qstate}")
            print(f"q0_b:\n{q0_b.qstate}")
            print(f"q0_b:\n{q0_a.qstate.dm}")
            print(f"q0_b:\n{q0_b.qstate.dm}")
            assert q0_a.qstate == q0_b.qstate  # check if entangled
            fid_b00 = qubitapi.fidelity([q0_a, q0_b], ketstates.b00)
            fid_b01 = qubitapi.fidelity([q0_a, q0_b], ketstates.b01)
            fid_b10 = qubitapi.fidelity([q0_a, q0_b], ketstates.b10)
            fid_b11 = qubitapi.fidelity([q0_a, q0_b], ketstates.b11)
            assert any(f > 0.99 for f in [fid_b00, fid_b01, fid_b10, fid_b11])

        self._host_alice = AliceHost
        self._host_bob = BobHost
        self._check_qmem = check_qmem
        self._check_cmem = None

    def test_entangle_ck_with_measure(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R0 1
        array R0 @0
        set R0 10
        array R0 @1
        set R0 1
        array R0 @2
        set R0 0
        set R1 0
        store R0 @2[R1]  // use virt ID 0 for EPR qubit
        set R0 20
        array R0 @3
        set R0 0
        set R1 0
        store R0 @3[R1]
        set R0 1
        set R1 1
        store R0 @3[R1]
        set R0 1
        array R0 @4
        set R0 1  // remote node ID = 1
        set R1 0  // EPR socket ID = 0
        set R2 2  // virtual IDs array = @2
        set R3 3  // arg array = @3
        set R4 1  // result array = @1
        create_epr R0 R1 R2 R3 R4
        set R0 0
        set R1 10
        wait_all @1[R0:R1]
        set R7 123  // test whether wait_all unblocks
        set Q0 0
        meas Q0 M0
        qfree Q0
        set R0 0
        store M0 @4[R0]
        ret_arr @0
        ret_arr @1
        ret_arr @2
        ret_arr @3
        ret_arr @4
        """

        SUBRT_2 = """
        # NETQASM 1.0
        # APPID 0
        set R0 1
        array R0 @0
        set R0 10
        array R0 @1
        set R0 1
        array R0 @2
        set R0 0
        set R1 0
        store R0 @2[R1]
        set R0 1
        array R0 @3
        set R0 0  // remote node ID = 0
        set R1 0  // EPR socket ID = 0
        set R2 2  // virtual IDs array = @2
        set R3 1  // result array = @1
        recv_epr R0 R1 R2 R3
        set R0 0
        set R1 10
        wait_all @1[R0:R1]
        set R7 123  // test whether wait_all unblocks
        set Q0 0
        meas Q0 M0
        qfree Q0
        set R0 0
        store M0 @3[R0]
        ret_arr @0
        ret_arr @1
        ret_arr @2
        ret_arr @3
        """

        class AliceHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 1)))
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        class BobHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 0)))
                subroutine = parse_text_subroutine(SUBRT_2, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        def check_cmem(
            app_mems_alice: Dict[int, AppMemory], app_mems_bob: Dict[int, AppMemory]
        ) -> None:
            mem_a = app_mems_alice[0]
            mem_b = app_mems_bob[0]

            assert mem_a.get_reg_value("R7") == 123
            assert mem_b.get_reg_value("R7") == 123

            bell_state_a = mem_a.get_array_value(1, 9)
            bell_state_b = mem_a.get_array_value(1, 9)
            assert bell_state_a == bell_state_b
            print(f"bell state: {bell_state_a}")

            outcome_a = mem_a.get_reg_value("M0")
            outcome_b = mem_b.get_reg_value("M0")
            print(f"outcomes: {outcome_a}, {outcome_b}")
            assert outcome_a == outcome_b

        self._host_alice = AliceHost
        self._host_bob = BobHost
        self._check_qmem = None
        self._check_cmem = check_cmem

    def test_entangle_md(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R0 10
        array R0 @0  // allocate result array
        set R0 20
        array R0 @1  // allocate arg array
        set R0 1
        set R1 0
        store R0 @1[R1]  // typ = 1 (MD)
        set R0 1
        set R1 1
        store R0 @1[R1] // num pairs = 1
        set R0 1  // remote node ID = 1
        set R1 0  // EPR socket ID = 0
        set R2 1  // arg array = @1
        set R3 0  // result array = @0
        create_epr R0 R1 C0 R2 R3
        """

        SUBRT_2 = """
        # NETQASM 1.0
        # APPID 0
        set R0 10
        array R0 @0   // allocate result array
        set R0 0  // remote node ID = 0
        set R1 0  // EPR socket ID = 0
        set R2 0  // result array = @0
        recv_epr R0 R1 C0 R2
        """

        class AliceHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 1)))
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        class BobHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 0)))
                subroutine = parse_text_subroutine(SUBRT_2, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        def check_cmem(
            app_mems_alice: Dict[int, AppMemory], app_mems_bob: Dict[int, AppMemory]
        ) -> None:
            mem_a = app_mems_alice[0]
            mem_b = app_mems_bob[0]
            outcome_a = mem_a.get_array_value(0, 2)
            basis_a = mem_a.get_array_value(0, 3)
            outcome_b = mem_b.get_array_value(0, 2)
            basis_b = mem_b.get_array_value(0, 3)
            basis_b = mem_b.get_array_value(0, 3)

            bell_state = mem_a.get_array_value(0, 9)
            bell_index = ketstates.BellIndex(bell_state)
            print(f"a: {outcome_a}, b: {outcome_b}")
            print(f"bases: a: {basis_a}, b: {basis_b}")
            print(f"bell index: {bell_index}")

            assert outcome_a in [0, 1]
            assert outcome_b in [0, 1]

            if (
                bell_index == ketstates.BellIndex.B00
                or bell_index == ketstates.BellIndex.B10
            ):
                assert outcome_a == outcome_b
            else:
                assert outcome_a != outcome_b

        self._host_alice = AliceHost
        self._host_bob = BobHost
        self._check_qmem = None
        self._check_cmem = check_cmem

    def test_entangle_md_with_wait(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R0 10
        array R0 @0  // allocate result array
        set R0 20
        array R0 @1  // allocate arg array
        set R0 1
        set R1 0
        store R0 @1[R1]  // typ = 1 (MD)
        set R0 1
        set R1 1
        store R0 @1[R1] // num pairs = 1
        set R0 1  // remote node ID = 1
        set R1 0  // EPR socket ID = 0
        set R2 1  // arg array = @1
        set R3 0  // result array = @0
        create_epr R0 R1 C0 R2 R3
        set R0 0
        set R1 10
        wait_all @0[R0:R1]
        set R7 123  // test if wait_all unblocks
        ret_arr @0
        ret_arr @1
        """

        SUBRT_2 = """
        # NETQASM 1.0
        # APPID 0
        set R0 10
        array R0 @0   // allocate result array
        set R0 0  // remote node ID = 0
        set R1 0  // EPR socket ID = 0
        set R2 0  // result array = @0
        recv_epr R0 R1 C0 R2
        set R0 0
        set R1 10
        wait_all @0[R0:R1]
        set R7 123  // test if wait_all unblocks
        ret_arr @0
        """

        class AliceHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 1)))
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        class BobHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 0)))
                subroutine = parse_text_subroutine(SUBRT_2, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        def check_cmem(
            app_mems_alice: Dict[int, AppMemory], app_mems_bob: Dict[int, AppMemory]
        ) -> None:
            mem_a = app_mems_alice[0]
            mem_b = app_mems_bob[0]

            assert mem_a.get_reg_value("R7") == 123
            assert mem_b.get_reg_value("R7") == 123

            outcome_a = mem_a.get_array_value(0, 2)
            basis_a = mem_a.get_array_value(0, 3)
            outcome_b = mem_b.get_array_value(0, 2)
            basis_b = mem_b.get_array_value(0, 3)
            print(f"bases: a: {basis_a}, b: {basis_b}")
            assert outcome_a in [0, 1]
            assert outcome_b in [0, 1]

            bell_state_a = mem_a.get_array_value(0, 9)
            bell_state_b = mem_a.get_array_value(0, 9)
            assert bell_state_a == bell_state_b
            print(f"bell state: {bell_state_a}")
            print(f"outcomes: {outcome_a}, {outcome_b}")
            if bell_state_a in [0, 3]:
                assert outcome_a == outcome_b
            else:
                assert outcome_a != outcome_b

        self._host_alice = AliceHost
        self._host_bob = BobHost
        self._check_qmem = None
        self._check_cmem = check_cmem

    def test_entangle_ck_with_post_routine(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R5 1
        array R5 @0
        set R5 10
        array R5 @1
        set R5 1
        array R5 @2
        set R5 0
        set R6 0
        store R5 @2[R6]
        set R5 20
        array R5 @3
        set R5 0
        set R6 0
        store R5 @3[R6]
        set R5 1
        set R6 1
        store R5 @3[R6]
        set R5 1
        set R6 0
        set R7 2
        set R8 3
        set R9 1
        create_epr R5 R6 R7 R8 R9
        set R0 0
        set R5 1
        beq R0 R5 53  // jump to end
        set R1 0
        set R2 0
        set R3 0
        set R4 0  // R4 = loop index
        set R5 10  // line 30, R5 = number of iterations
        beq R4 R5 36  // exit loop
        add R1 R1 R0
        set R5 1
        add R4 R4 R5
        jmp 30
        set R5 1
        add R2 R0 R5
        set R4 0
        set R5 10
        beq R4 R5 45
        add R3 R3 R2
        set R5 1
        add R4 R4 R5
        jmp 39
        wait_all @1[R1:R3]
        load Q0 @2[R0]
        meas Q0 M0
        qfree Q0
        store M0 @0[R0]
        set R5 1
        add R0 R0 R5
        jmp 24
        ret_arr @0
        ret_arr @1
        ret_arr @2
        ret_arr @3
        """

        SUBRT_2 = """
        # NETQASM 1.0
        # APPID 0
        set R5 1
        array R5 @0
        set R5 10
        array R5 @1
        set R5 1
        array R5 @2
        set R5 0
        set R6 0
        store R5 @2[R6]
        set R5 0
        set R6 0
        set R7 2
        set R8 1
        recv_epr R5 R6 R7 R8
        set R0 0
        set R5 1
        beq R0 R5 44
        set R1 0
        set R2 0
        set R3 0
        set R4 0
        set R5 10
        beq R4 R5 27
        add R1 R1 R0
        set R5 1
        add R4 R4 R5
        jmp 21
        set R5 1
        add R2 R0 R5
        set R4 0
        set R5 10
        beq R4 R5 36
        add R3 R3 R2
        set R5 1
        add R4 R4 R5
        jmp 30
        wait_all @1[R1:R3]
        load Q0 @2[R0]
        meas Q0 M0
        qfree Q0
        store M0 @0[R0]
        set R5 1
        add R0 R0 R5
        jmp 15
        ret_arr @0
        ret_arr @1
        ret_arr @2
        """

        class AliceHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 1)))
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        class BobHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, 0, 0)))
                subroutine = parse_text_subroutine(SUBRT_2, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                self.send_qnos_msg(bytes(StopAppMessage(app_id)))

        def check_cmem(
            app_mems_alice: Dict[int, AppMemory], app_mems_bob: Dict[int, AppMemory]
        ) -> None:
            mem_a = app_mems_alice[0]
            mem_b = app_mems_bob[0]

            outcome_a = mem_a.get_reg_value("M0")
            outcome_b = mem_b.get_reg_value("M0")
            assert outcome_a in [0, 1]
            assert outcome_b in [0, 1]

            bell_state_a = mem_a.get_array_value(1, 9)
            bell_state_b = mem_a.get_array_value(1, 9)
            assert bell_state_a == bell_state_b
            print(f"bell state: {bell_state_a}")
            print(f"outcomes: {outcome_a}, {outcome_b}")
            assert outcome_a == outcome_b

        self._host_alice = AliceHost
        self._host_bob = BobHost
        self._check_qmem = None
        self._check_cmem = check_cmem


if __name__ == "__main__":
    unittest.main()
