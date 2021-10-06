import unittest
from typing import Generator, Optional, Type

import netsquid as ns
from netqasm.backend.messages import InitNewAppMessage, SubroutineMessage
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.components import QuantumProcessor
from netsquid.qubits import ketstates, qubitapi

from pydynaa import EventExpression
from squidasm.run.stack.build import build_nv_qdevice
from squidasm.run.stack.config import NVQDeviceConfig
from squidasm.sim.stack.common import AppMemory
from squidasm.sim.stack.host import Host
from squidasm.sim.stack.stack import NodeStack


class TestSingleNode(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        qdevice = build_nv_qdevice(
            "nv_qdevice_alice", cfg=NVQDeviceConfig.perfect_config()
        )
        self._node = NodeStack("alice", qdevice_type="nv", qdevice=qdevice)

        self._host: Optional[Type[Host]] = None

    def tearDown(self) -> None:
        self._node.subprotocols[f"{self._node.name}_host_protocol"] = self._host(
            self._node.host_comp
        )
        self._node.start()
        ns.sim_run()
        if self._check_qmem:
            self._check_qmem(self._node.qdevice)

    def test_register_app(self):
        class TestHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0

        self._host = TestHost
        self._check_qmem = None

    def test_classical_instructions(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set R0 0
        set R1 1
        set R2 20
        """

        class TestHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("R0") == 0
                assert app_mem.get_reg_value("R1") == 1
                assert app_mem.get_reg_value("R2") == 20

        self._host = TestHost
        self._check_qmem = None

    def test_quantum_instructions(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set Q0 0
        qalloc Q0
        init Q0
        """

        class TestHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("Q0") == 0

        def check_qmem(qdevice: QuantumProcessor) -> None:
            [q0] = qdevice.peek(0, skip_noise=True)
            assert qubitapi.fidelity(q0, ketstates.s0) > 0.999

        self._host = TestHost
        self._check_qmem = check_qmem

    def test_quantum_instructions_2(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set Q0 0
        qalloc Q0
        init Q0
        meas Q0 M0
        """

        class TestHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("Q0") == 0
                assert app_mem.get_reg_value("M0") == 0

        self._host = TestHost
        self._check_qmem = None

    def test_quantum_instructions_3(self):
        SUBRT_1 = """
        # NETQASM 1.0
        # APPID 0
        set Q0 0
        qalloc Q0
        init Q0
        rot_x Q0 16 4
        """

        class TestHost(Host):
            def run(self) -> Generator[EventExpression, None, None]:
                self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=2)))
                app_id = yield from self.receive_qnos_msg()
                assert app_id == 0
                subroutine = parse_text_subroutine(SUBRT_1, flavour=NVFlavour())
                subroutine.app_id = app_id
                self.send_qnos_msg(bytes(SubroutineMessage(subroutine)))
                app_mem = yield from self.receive_qnos_msg()
                assert isinstance(app_mem, AppMemory)
                assert app_mem.get_reg_value("Q0") == 0

        def check_qmem(qdevice: QuantumProcessor) -> None:
            [q0] = qdevice.peek(0, skip_noise=True)
            print(qubitapi.reduced_dm(q0))
            assert qubitapi.fidelity(q0, ketstates.s1) > 0.999

        self._host = TestHost
        self._check_qmem = check_qmem


if __name__ == "__main__":
    unittest.main()
