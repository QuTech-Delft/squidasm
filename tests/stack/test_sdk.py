import unittest
from typing import Any, Dict, Generator, Optional

import netsquid as ns
from netqasm.sdk.qubit import Qubit
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
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class TestSdkSingleNode(unittest.TestCase):
    def setUp(self) -> None:
        config = NVQDeviceConfig.perfect_config()
        ns.sim_reset()
        network_cfg = create_single_node_network(qdevice_typ="nv", qdevice_cfg=config)
        self.network = _setup_network(network_cfg)
        self._node = self.network.stacks["Alice"]

        self._program: Optional[Program] = None

    def tearDown(self) -> None:
        assert self._program is not None
        self._node.host.enqueue_program(self._program, 1)
        LogManager.set_log_level("INFO")
        _run(self.network)
        if self._check_qmem:
            self._check_qmem(self._node.qdevice)

    def test_1(self):
        class TestProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="test_program",
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
        ns.nodes.node._node_ID_counter = -1
        network_cfg = create_2_node_network(
            qlink_typ="depolarise",
            qlink_cfg=DepolariseQLinkConfig(fidelity=1, prob_success=0.5, t_cycle=10),
            qdevice_typ="nv",
            qdevice_cfg=NVQDeviceConfig.perfect_config(),
        )
        self.network = _setup_network(network_cfg)

        self._alice = self.network.stacks["Alice"]
        self._bob = self.network.stacks["Bob"]

        self._prog_alice: Optional[Program] = None
        self._prog_bob: Optional[Program] = None

    def tearDown(self) -> None:
        assert self._prog_alice is not None
        assert self._prog_bob is not None

        self._alice.host.enqueue_program(self._prog_alice)
        self._bob.host.enqueue_program(self._prog_bob)

        # ns.set_qstate_formalism(ns.QFormalism.DM)
        _run(self.network)

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
                    csockets=["Bob"],
                    epr_sockets=["Bob"],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                epr_socket = context.epr_sockets["Bob"]

                csocket = context.csockets["Bob"]
                msg = yield from csocket.recv()
                print(f"got message from Bob: {msg}")

                # q = Qubit(conn)
                # q.X()
                # m = q.measure()
                # yield from conn.flush()

                # print(f"m = {m}")

                q = epr_socket.create_keep()[0]
                epr_outcome = q.measure()
                yield from conn.flush()
                print(f"epr_outcome = {epr_outcome}")

        class ServerProgram(Program):
            @property
            def meta(self) -> ProgramMeta:
                return ProgramMeta(
                    name="server_program",
                    csockets=["Alice"],
                    epr_sockets=["Alice"],
                    max_qubits=2,
                )

            def run(
                self, context: ProgramContext
            ) -> Generator[EventExpression, None, Dict[str, Any]]:
                conn = context.connection
                epr_socket = context.epr_sockets["Alice"]
                csocket = context.csockets["Alice"]

                csocket.send("hello")

                # q = Qubit(conn)
                # q.X()
                # m = q.measure()
                # print(f"time before measuring: {ns.sim_time()}")
                # yield from conn.flush()
                # print(f"time after measuring: {ns.sim_time()}")

                # print(f"m = {m}")

                q = epr_socket.recv_keep()[0]
                epr_outcome = q.measure()
                yield from conn.flush()
                print(f"epr_outcome = {epr_outcome}")

        self._prog_alice = ClientProgram()
        self._prog_bob = ServerProgram()
        self._check_qmem = None
        self._check_cmem = None


if __name__ == "__main__":
    unittest.main()
