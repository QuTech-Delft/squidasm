import unittest
from typing import Generator, Optional, Type

import netsquid as ns
from netqasm.lang.parsing import parse_text_subroutine
from netsquid.components import QuantumProcessor
from netsquid.qubits import ketstates, qubitapi
from netsquid_netbuilder.modules.qdevices.nv import NVQDeviceConfig
from netsquid_netbuilder.modules.qlinks.depolarise import DepolariseQLinkConfig
from netsquid_netbuilder.util.network_generation import create_2_node_network

from pydynaa import EventExpression
from squidasm.run.stack.run import _run, _setup_network
from squidasm.sim.stack.handler import Handler


class TestHandler(unittest.TestCase):
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

        # to be set by test case
        self._alice_handler: Optional[Type[Handler]] = None
        self._bob_handler: Optional[Type[Handler]] = None

    def tearDown(self) -> None:
        # ns.set_qstate_formalism(ns.QFormalism.DM)
        _run(self.network)

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

        class TestHandler(Handler):
            def run(self) -> Generator[EventExpression, None, None]:
                app = self._next_app()
                if app is not None:
                    while True:
                        subrt = app.next_subroutine()
                        if subrt is None:
                            break
                        app_mem = yield from self.assign_processor(app.id, subrt)
                        self._send_host_msg(app_mem)

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

        self._alice_handler = TestHandler
        self._bob_handler = TestHandler
        self._check_qmem = check_qmem
        self._check_cmem = None

        self._alice.qnos.handler = self._alice_handler(
            self._alice.qnos_comp.handler_comp, self._alice.qnos
        )
        self._bob.qnos.handler = self._bob_handler(
            self._bob.qnos_comp.handler_comp, self._bob.qnos
        )

        app_id_a = self._alice.qnos.handler.init_new_app(1)
        self._alice.qnos.handler.open_epr_socket(app_id_a, 0, 1)
        subrt_a = parse_text_subroutine(SUBRT_1)
        self._alice.qnos.handler.add_subroutine(app_id_a, subrt_a)

        app_id_b = self._bob.qnos.handler.init_new_app(1)
        self._bob.qnos.handler.open_epr_socket(app_id_b, 0, 0)
        subrt_b = parse_text_subroutine(SUBRT_2)
        self._bob.qnos.handler.add_subroutine(app_id_b, subrt_b)


if __name__ == "__main__":
    unittest.main()
