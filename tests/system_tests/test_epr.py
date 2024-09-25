import unittest
from dataclasses import dataclass, field
from typing import Any, List

import netsquid as ns
from netsquid.qubits.ketstates import BellIndex
from netsquid_netbuilder.modules.qlinks.depolarise import DepolariseQLinkConfig
from netsquid_netbuilder.modules.qlinks.heralded_double_click import (
    HeraldedDoubleClickQLinkConfig,
)
from netsquid_netbuilder.modules.qlinks.heralded_single_click import (
    HeraldedSingleClickQLinkConfig,
)
from netsquid_netbuilder.modules.qlinks.perfect import PerfectQLinkConfig
from netsquid_netbuilder.util.fidelity import calculate_fidelity_epr
from netsquid_netbuilder.util.network_generation import (
    create_2_node_network,
    create_complete_graph_network_simplified,
)

from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util.util import get_qubit_state


@dataclass
class EPRRequest:
    peer_name: str
    """Name of the remote peer for the EPR request"""
    is_create: bool
    """Flag for indicating that this node is to use the `create_xxx` or `recv_xxx` method"""
    kwargs: dict = field(default_factory=dict)
    """Optional extra arguments for the EPR request"""


class EPRKeepProgram(Program):
    def __init__(self, name: str, requests: List[EPRRequest]):
        """
        Test program that executes a number of requests for epr generation and keeping the qubit.
        It logs various metrics of the requests, like: total completion time, qubit states and measurement results.
        :param name: Node name running the program
        :param requests: List of requests for entanglement generation.
        """
        self.name = name
        self.requests = requests

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="test_program",
            csockets=[req.peer_name for req in self.requests],
            epr_sockets=[req.peer_name for req in self.requests],
            max_qubits=100,
        )

    def run(self, context: ProgramContext):
        qubits = []
        for req in self.requests:
            epr_socket = context.epr_sockets[req.peer_name]
            if req.is_create:
                qubits += epr_socket.create_keep(**req.kwargs)
            else:
                qubits += epr_socket.recv_keep(**req.kwargs)

        start_time = ns.sim_time()
        yield from context.connection.flush()
        epr_completion_time = ns.sim_time() - start_time
        # Wait for all other nodes to complete
        # as bell state correction may need to occur on other node and that affects the qubit state
        for csocket in context.csockets.values():
            csocket.send("Handshake")
        for csocket in context.csockets.values():
            yield from csocket.recv()
        qubit_states = [get_qubit_state(q, self.name, full_state=True) for q in qubits]
        measurements = [qubit.measure() for qubit in qubits]
        yield from context.connection.flush()

        return {
            "name": self.name,
            "epr_completion_time": epr_completion_time,
            "measurements": [int(m) for m in measurements],
            "qubit_states": qubit_states,
        }


class TestEPR(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        ns.set_qstate_formalism(ns.QFormalism.DM)

    def tearDown(self) -> None:
        pass

    @staticmethod
    def _get_result(results: List[List[dict]], node: str, key: str) -> Any:
        """Tool for retrieving a result from a certain node and key out of the result list returned by run()"""
        for r in results:
            if r[0]["name"] == node:
                return r[0][key]
        raise KeyError(f"Could not find the results for node: {node}")

    def test_single_qubit_CK_two_nodes(self):
        """Check that delay is as expected and measurement results are identical for simple scenario"""
        cdelay = 10
        qdelay = 15
        num_req = 4
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice", "Bob"], clink_delay=cdelay, link_delay=qdelay
        )
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        # Expected completion time has 2 * cdelay -> Handshake Alice to Bob & return
        # + qdelay is due to 1 round of EPR generation after which results are in
        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time"),
            (cdelay * 2 + qdelay) * num_req,
            delta=1e-9,
        )

        for m_alice, m_bob in zip(
            self._get_result(results, "Alice", "measurements"),
            self._get_result(results, "Bob", "measurements"),
        ):
            self.assertEqual(m_alice, m_bob)

    def test_multi_qubit_CK_two_nodes(self):
        """Check that delay is as expected and measurement results are identical
        when requests ask for multiple qubits"""
        cdelay = 24
        qdelay = 77
        num_req = 3
        num_qubits = 6
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice", "Bob"], clink_delay=cdelay, link_delay=qdelay
        )
        alice_req = [
            EPRRequest("Bob", is_create=True, kwargs={"number": num_qubits})
            for _ in range(num_req)
        ]
        bob_req = [
            EPRRequest("Alice", is_create=False, kwargs={"number": num_qubits})
            for _ in range(num_req)
        ]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time"),
            (cdelay * 2 + qdelay * num_qubits) * num_req,
            delta=1e-9,
        )

        for m_alice, m_bob in zip(
            self._get_result(results, "Alice", "measurements"),
            self._get_result(results, "Bob", "measurements"),
        ):
            self.assertEqual(m_alice, m_bob)

    def test_CK_three_nodes(self):
        """Check that delay is as expected and measurement results are identical
        when using multiple nodes and requests to each other."""
        cdelay = 66
        qdelay = 10
        num_req = 5
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice", "Bob", "Charlie"],
            clink_delay=cdelay,
            link_delay=qdelay,
        )
        # Setup requests such that the ordering is Alice -> Bob, Bob -> Charlie, Charlie -> Alice
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)] + [
            EPRRequest("Charlie", is_create=False) for _ in range(num_req)
        ]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)] + [
            EPRRequest("Charlie", is_create=True) for _ in range(num_req)
        ]
        charlie_req = [EPRRequest("Bob", is_create=False) for _ in range(num_req)] + [
            EPRRequest("Alice", is_create=True) for _ in range(num_req)
        ]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        charlie_program = EPRKeepProgram("Charlie", charlie_req)

        results = run(
            config=network_cfg,
            programs={
                "Alice": alice_program,
                "Bob": bob_program,
                "Charlie": charlie_program,
            },
            num_times=1,
        )

        req_pair_completion_time = (cdelay * 2 + qdelay) * num_req
        # Bob is fully finished after 2 rounds, Alice & Charlie are doing the third and last round together
        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time"),
            req_pair_completion_time * 3,
            delta=1e-9,
        )
        self.assertAlmostEqual(
            self._get_result(results, "Bob", "epr_completion_time"),
            req_pair_completion_time * 2,
            delta=1e-9,
        )
        self.assertAlmostEqual(
            self._get_result(results, "Charlie", "epr_completion_time"),
            req_pair_completion_time * 3,
            delta=1e-9,
        )

        for m_alice, m_bob in zip(
            self._get_result(results, "Alice", "measurements")[:num_req],
            self._get_result(results, "Bob", "measurements")[:num_req],
        ):
            self.assertEqual(m_alice, m_bob)

        for m_charlie, m_bob in zip(
            self._get_result(results, "Charlie", "measurements")[:num_req],
            self._get_result(results, "Bob", "measurements")[num_req:],
        ):
            self.assertEqual(m_charlie, m_bob)

        for m_charlie, m_alice in zip(
            self._get_result(results, "Charlie", "measurements")[num_req:],
            self._get_result(results, "Alice", "measurements")[num_req:],
        ):
            self.assertEqual(m_charlie, m_alice)

    def test_perfect_link(self):
        """Test that perfect link generates a perfect phi+ state and after the exact delay specified"""
        delay = 2020
        num_req = 5

        network_cfg = create_2_node_network(
            qlink_typ="perfect",
            qlink_cfg=PerfectQLinkConfig(state_delay=delay),
            clink_typ="instant",
        )
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time"),
            delay * num_req,
            delta=1e-9,
        )

        for qubit_state in self._get_result(results, "Alice", "qubit_states"):
            self.assertAlmostEqual(
                calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS), 1, delta=1e-4
            )

    def test_depolarise_link(self):
        """Test that depolarise link with perfect settings generates a perfect phi+ state
        and after the exact delay specified"""

        delay = 766
        num_req = 7

        network_cfg = create_2_node_network(
            qlink_typ="depolarise",
            qlink_cfg=DepolariseQLinkConfig(t_cycle=delay, fidelity=1, prob_success=1),
            clink_typ="instant",
        )
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time"),
            delay * num_req,
            delta=1e-9,
        )

        for qubit_state in self._get_result(results, "Alice", "qubit_states"):
            self.assertAlmostEqual(
                calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS), 1, delta=1e-4
            )

    @unittest.expectedFailure  # Running multiple requests at the same time, results in incorrect bell states provided
    def test_single_click_link(self):
        """Test that single click link with perfect settings generates a perfect phi+ state
        and the completion time is a multiple of the expected cycle time"""
        delay = 20
        num_req = 6

        network_cfg = create_2_node_network(
            qlink_typ="heralded-single-click",
            qlink_cfg=HeraldedSingleClickQLinkConfig(
                length=delay,
                p_loss_init=0,
                p_loss_length=0,
                speed_of_light=1e9,
                emission_fidelity=1,
            ),
            clink_typ="instant",
        )
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time") % delay,
            0,
            delta=1e-9,
        )

        for qubit_state in self._get_result(results, "Alice", "qubit_states"):
            self.assertAlmostEqual(
                calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS), 1, delta=1e-4
            )

    @unittest.expectedFailure  # Running multiple requests at the same time, results in incorrect bell states provided
    def test_double_click_link(self):
        """Test that double click link with perfect settings generates a perfect phi+ state
        and the completion time is a multiple of the expected cycle time"""
        delay = 75
        num_req = 8

        network_cfg = create_2_node_network(
            qlink_typ="heralded-double-click",
            qlink_cfg=HeraldedDoubleClickQLinkConfig(
                length=delay,
                p_loss_init=0,
                p_loss_length=0,
                speed_of_light=1e9,
                emission_fidelity=1,
            ),
            clink_typ="instant",
        )
        alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
        bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

        alice_program = EPRKeepProgram("Alice", alice_req)
        bob_program = EPRKeepProgram("Bob", bob_req)
        results = run(
            config=network_cfg,
            programs={"Alice": alice_program, "Bob": bob_program},
            num_times=1,
        )

        self.assertAlmostEqual(
            self._get_result(results, "Alice", "epr_completion_time") % delay,
            0,
            delta=1e-9,
        )

        for qubit_state in self._get_result(results, "Alice", "qubit_states"):
            self.assertAlmostEqual(
                calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS), 1, delta=1e-4
            )

    def test_single_click_link_temp_single_req(self):
        """Temporary test falling in for `test_single_click_link`,
        this test uses only 1 request at the time to avoid the bug in the original test"""
        delay = 20
        num_req = 1
        for _ in range(20):
            ns.sim_reset()

            network_cfg = create_2_node_network(
                qlink_typ="heralded-single-click",
                qlink_cfg=HeraldedSingleClickQLinkConfig(
                    length=delay,
                    p_loss_init=0,
                    p_loss_length=0,
                    speed_of_light=1e9,
                    emission_fidelity=1,
                ),
                clink_typ="instant",
            )
            alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
            bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

            alice_program = EPRKeepProgram("Alice", alice_req)
            bob_program = EPRKeepProgram("Bob", bob_req)
            results = run(
                config=network_cfg,
                programs={"Alice": alice_program, "Bob": bob_program},
                num_times=1,
            )

            self.assertAlmostEqual(
                self._get_result(results, "Alice", "epr_completion_time") % delay,
                0,
                delta=1e-9,
            )

            for qubit_state in self._get_result(results, "Alice", "qubit_states"):
                self.assertAlmostEqual(
                    calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS),
                    0.99,  # This is currently the hardcoded value for MINIMUM_FIDELITY in netstack.py
                    delta=5e-2,
                )

    def test_double_click_link_temp_single_req(self):
        """Temporary test falling in for `test_double_click_link`,
        this test uses only 1 request at the time to avoid the bug in the original test"""
        delay = 75
        num_req = 1

        for _ in range(20):
            ns.sim_reset()
            network_cfg = create_2_node_network(
                qlink_typ="heralded-double-click",
                qlink_cfg=HeraldedDoubleClickQLinkConfig(
                    length=delay,
                    p_loss_init=0,
                    p_loss_length=0,
                    speed_of_light=1e9,
                    emission_fidelity=1,
                ),
                clink_typ="instant",
            )
            alice_req = [EPRRequest("Bob", is_create=True) for _ in range(num_req)]
            bob_req = [EPRRequest("Alice", is_create=False) for _ in range(num_req)]

            alice_program = EPRKeepProgram("Alice", alice_req)
            bob_program = EPRKeepProgram("Bob", bob_req)
            results = run(
                config=network_cfg,
                programs={"Alice": alice_program, "Bob": bob_program},
                num_times=1,
            )

            self.assertAlmostEqual(
                self._get_result(results, "Alice", "epr_completion_time") % delay,
                0,
                delta=1e-9,
            )

            for qubit_state in self._get_result(results, "Alice", "qubit_states"):
                self.assertAlmostEqual(
                    calculate_fidelity_epr(qubit_state, BellIndex.PHI_PLUS),
                    1,
                    delta=1e-4,
                )


if __name__ == "__main__":
    unittest.main()
