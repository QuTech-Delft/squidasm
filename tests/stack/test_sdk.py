import unittest
from typing import Any, Dict, Generator, Optional

import netsquid as ns
from netqasm.sdk.qubit import Qubit
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
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.sim.stack.stack import NodeStack


class TestSdkSingleNode(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        qdevice = build_nv_qdevice(
            "nv_qdevice_alice", cfg=NVQDeviceConfig.perfect_config()
        )
        self._node = NodeStack("alice", qdevice_type="nv", qdevice=qdevice)

        self._program: Optional[Program] = None

    def tearDown(self) -> None:
        assert self._program is not None
        self._node.host.enqueue_program(self._program, 1)
        self._node.start()
        ns.sim_run()
        if self._check_qmem:
            self._check_qmem(self._node.qdevice)

    def test_1(self):
        class TestProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="test_program",
                    parameters={},
                    csockets=[],
                    epr_sockets=[],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                q = Qubit(conn)
                q.X()
                yield from conn.flush()

        def check_qmem(qdevice: QuantumProcessor) -> None:
            [q0] = qdevice.peek(0, skip_noise=True)
            assert qubitapi.fidelity(q0, ketstates.s1) > 0.999

        self._program = TestProgram()
        self._check_qmem = check_qmem

    def test_2(self):
        class TestProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="test_program",
                    parameters={},
                    csockets=[],
                    epr_sockets=[],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                q1 = Qubit(conn)
                q1.X()
                q2 = Qubit(conn)
                q1.cnot(q2)
                yield from conn.flush()

        def check_qmem(qdevice: QuantumProcessor) -> None:
            [q0] = qdevice.peek(0, skip_noise=True)
            [q1] = qdevice.peek(1, skip_noise=True)
            assert qubitapi.fidelity(q0, ketstates.s1) > 0.999
            assert qubitapi.fidelity(q1, ketstates.s1) > 0.999

        self._program = TestProgram()
        self._check_qmem = check_qmem

    def test_3(self):
        class TestProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="test_program",
                    parameters={},
                    csockets=[],
                    epr_sockets=[],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                q1 = Qubit(conn)
                q2 = Qubit(conn)
                q2.H()
                q2.cnot(q1)
                yield from conn.flush()

        def check_qmem(qdevice: QuantumProcessor) -> None:
            [q0] = qdevice.peek(0, skip_noise=True)
            [q1] = qdevice.peek(1, skip_noise=True)
            assert q0.qstate == q1.qstate
            print(f"state:\n{q0.qstate.dm}")
            fid = qubitapi.fidelity([q0, q1], ketstates.b00)
            print(fid)
            assert fid > 0.9

        self._program = TestProgram()
        self._check_qmem = check_qmem


class TestSdkTwoNodes(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        alice_qdevice = build_nv_qdevice(
            "nv_qdevice_alice", cfg=NVQDeviceConfig.perfect_config()
        )
        self._alice = NodeStack(
            "alice", qdevice_type="nv", qdevice=alice_qdevice, node_id=0
        )

        bob_qdevice = build_nv_qdevice(
            "nv_qdevice_bob", cfg=NVQDeviceConfig.perfect_config()
        )
        self._bob = NodeStack("bob", qdevice_type="nv", qdevice=bob_qdevice, node_id=1)

        self._prog_alice: Optional[Program] = None
        self._prog_bob: Optional[Program] = None

    def tearDown(self) -> None:
        assert self._prog_alice is not None
        assert self._prog_bob is not None
        # link_dist = PerfectStateMagicDistributor(
        #     nodes=[self._alice.node, self._bob.node]
        # )
        link_dist = NVSingleClickMagicDistributor(
            nodes=[self._alice.node, self._bob.node],
            length_A=0.001,
            length_B=0.001,
            full_cycle=0.001,
            t_cycle=10,
        )
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[self._alice.node, self._bob.node],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        self._alice.assign_ll_protocol(link_prot)
        self._bob.assign_ll_protocol(link_prot)

        self._alice.host.enqueue_program(self._prog_alice)
        self._bob.host.enqueue_program(self._prog_bob)

        self._alice.connect_to(self._bob)
        NetSquidContext.set_nodes({0: "alice", 1: "bob"})

        link_prot.start()
        self._alice.start()
        self._bob.start()

        # ns.set_qstate_formalism(ns.QFormalism.DM)
        ns.sim_run()
        if self._check_qmem:
            self._check_qmem(self._alice.qdevice, self._bob.qdevice)
        if self._check_cmem:
            self._check_cmem(self._alice.qnos.app_memories, self._bob.qnos.app_memories)

    def test_1(self):
        class ClientProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="client_program",
                    parameters={},
                    csockets=["bob"],
                    epr_sockets=["bob"],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                epr_socket = context.epr_sockets["bob"]

                csocket = context.csockets["bob"]
                msg = yield from csocket.recv()
                print(f"got message from bob: {msg}")

                q = Qubit(conn)
                q.X()
                m = q.measure()
                yield from conn.flush()

                print(f"m = {m}")

                q = epr_socket.create()[0]
                epr_outcome = q.measure()
                yield from conn.flush()
                print(f"epr_outcome = {epr_outcome}")

        class ServerProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="server_program",
                    parameters={},
                    csockets=["alice"],
                    epr_sockets=["alice"],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                epr_socket = context.epr_sockets["alice"]
                csocket = context.csockets["alice"]

                csocket.send("hello")

                q = Qubit(conn)
                q.X()
                m = q.measure()
                print(f"time before measuring: {ns.sim_time()}")
                yield from conn.flush()
                print(f"time after measuring: {ns.sim_time()}")

                print(f"m = {m}")

                q = epr_socket.recv()[0]
                epr_outcome = q.measure()
                yield from conn.flush()
                print(f"epr_outcome = {epr_outcome}")

        self._prog_alice = ClientProgram()
        self._prog_bob = ServerProgram()
        self._check_qmem = None
        self._check_cmem = None


if __name__ == "__main__":
    unittest.main()
