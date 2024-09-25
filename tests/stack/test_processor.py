import unittest
from typing import Dict, Generator

import netsquid as ns
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.components import QuantumProcessor
from netsquid.qubits import ketstates, qubitapi
from netsquid_netbuilder.modules.qdevices.nv import NVQDeviceConfig
from netsquid_netbuilder.modules.qlinks.depolarise import DepolariseQLinkConfig
from netsquid_netbuilder.util.network_generation import (
    create_2_node_network,
    create_single_node_network,
)

from pydynaa import EventExpression
from squidasm.run.stack.run import _run, _setup_network
from squidasm.sim.stack.common import AppMemory
from squidasm.sim.stack.processor import NVProcessor


class TestProcessorTwoNodes(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        ns.nodes.node._node_ID_counter = -1
        network_cfg = create_2_node_network(
            qlink_typ="depolarise",
            qlink_cfg=DepolariseQLinkConfig(fidelity=1, prob_success=0.5, t_cycle=10),
            qdevice_typ="nv",
            qdevice_cfg=NVQDeviceConfig(),
        )
        self.network = _setup_network(network_cfg)

        self._alice = self.network.stacks["Alice"]
        self._bob = self.network.stacks["Bob"]

    def tearDown(self) -> None:
        # ns.set_qstate_formalism(ns.QFormalism.DM)
        _run(self.network)

        if self._check_qmem:
            self._check_qmem(self._alice.qdevice, self._bob.qdevice)
        if self._check_cmem:
            self._check_cmem(self._alice.qnos.app_memories, self._bob.qnos.app_memories)

    def test_entangle_ck(self):
        APP_ID = 0

        SUBRT_1 = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set R0 0
        set R1 1
        set R2 20
        array R2 @0
        store R0 @0[R0]
        store R1 @0[R1]
        create_epr R1 R0 R0 R0 R0
        """

        SUBRT_2 = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set R0 0
        set R1 1
        set R2 20
        array R2 @0
        store R0 @0[R0]
        store R1 @0[R1]
        recv_epr R0 R0 R0 R0
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT_1)
                yield from self.execute_subroutine(subroutine)

        class BobProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT_2)
                yield from self.execute_subroutine(subroutine)

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
            print(f"fidelities: {fid_b00}, {fid_b01}, {fid_b10}, {fid_b11}")
            assert any(f > 0.99 for f in [fid_b00, fid_b01, fid_b10, fid_b11])

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )
        self._bob.qnos.handler = BobProcessor(
            self._bob.qnos_comp.processor_comp, self._bob.qnos
        )

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.netstack.open_epr_socket(APP_ID, 0, 1)
        self._bob.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._bob.qnos.netstack.open_epr_socket(APP_ID, 0, 0)


class TestProcessorSingleNode(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        config = NVQDeviceConfig.perfect_config()
        config.num_qubits = 3
        network_cfg = create_single_node_network(qdevice_typ="nv", qdevice_cfg=config)
        self.network = _setup_network(network_cfg)
        self._alice = self.network.stacks["Alice"]

    def tearDown(self) -> None:
        _run(self.network)

        if self._check_qmem:
            self._check_qmem(self._alice.qdevice)
        if self._check_cmem:
            self._check_cmem(self._alice.qnos.app_memories)

    def test0(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            assert qubitapi.fidelity(q0, ketstates.s0) > 0.99

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test1(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        rot_x Q0 16 4
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            assert qubitapi.fidelity(q0, ketstates.s1) > 0.99

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test2(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        rot_y Q0 16 4
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            assert qubitapi.fidelity(q0, ketstates.s1) > 0.99

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test3(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        rot_z Q0 16 4
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            assert qubitapi.fidelity(q0, ketstates.s0) > 0.99

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test4(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        rot_y Q0 8 4
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            assert qubitapi.fidelity(q0, ketstates.h0) > 0.99

        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test5(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        meas Q0 M0
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_cmem(app_mems_alice: Dict[int, AppMemory]) -> None:
            mem = app_mems_alice[0]
            outcome = mem.get_reg_value("M0")
            assert outcome == 0

        self._check_qmem = None
        self._check_cmem = check_cmem

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test6(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        qalloc Q0
        init Q0
        rot_y Q0 16 4
        meas Q0 M0
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_cmem(app_mems_alice: Dict[int, AppMemory]) -> None:
            mem = app_mems_alice[0]
            outcome = mem.get_reg_value("M0")
            assert outcome == 1

        self._check_qmem = None
        self._check_cmem = check_cmem

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test7(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        set Q1 1
        qalloc Q0
        qalloc Q1
        init Q0
        init Q1
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            [q0] = qdevice_alice.peek(0, skip_noise=True)
            [q1] = qdevice_alice.peek(1, skip_noise=True)
            print(f"q0:\n{q0.qstate}")
            print(f"q1:\n{q1.qstate}")
            assert qubitapi.fidelity(q0, ketstates.s0) > 0.99
            assert qubitapi.fidelity(q1, ketstates.s0) > 0.99

        def check_cmem(app_mems_alice: Dict[int, AppMemory]) -> None:
            pass

        self._check_qmem = check_qmem
        self._check_cmem = check_cmem

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test8(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        set Q1 1
        qalloc Q0
        qalloc Q1
        init Q0
        init Q1
        meas Q0 M0
        qfree Q0
        meas Q1 M1
        qfree Q1
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            pass

        def check_cmem(app_mems_alice: Dict[int, AppMemory]) -> None:
            mem = app_mems_alice[0]
            outcome0 = mem.get_reg_value("M0")
            outcome1 = mem.get_reg_value("M1")
            assert outcome0 == 0
            assert outcome1 == 0

        self._check_qmem = check_qmem
        self._check_cmem = check_cmem

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )

    def test9(self):
        APP_ID = 0

        SUBRT = f"""
        # NETQASM 1.0
        # APPID {APP_ID}
        set Q0 0
        set Q1 1
        qalloc Q0
        qalloc Q1
        init Q0
        init Q1
        meas Q1 M1
        qfree Q1
        meas Q0 M0
        qfree Q0
        """

        class AliceProcessor(NVProcessor):
            def run(self) -> Generator[EventExpression, None, None]:
                subroutine = parse_text_subroutine(SUBRT, flavour=NVFlavour())
                yield from self.execute_subroutine(subroutine)

        def check_qmem(qdevice_alice: QuantumProcessor) -> None:
            pass

        def check_cmem(app_mems_alice: Dict[int, AppMemory]) -> None:
            mem = app_mems_alice[0]
            outcome0 = mem.get_reg_value("M0")
            outcome1 = mem.get_reg_value("M1")
            assert outcome0 == 0
            assert outcome1 == 0

        self._check_qmem = check_qmem
        self._check_cmem = check_cmem

        self._alice.qnos.app_memories[APP_ID] = AppMemory(APP_ID, 2)
        self._alice.qnos.processor = AliceProcessor(
            self._alice.qnos_comp.processor_comp, self._alice.qnos
        )


if __name__ == "__main__":
    unittest.main()
