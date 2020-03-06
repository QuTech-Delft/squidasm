import logging
import numpy as np
from time import sleep

from netqasm.sdk import Qubit
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications


def test_two_nodes():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        logging.debug("Starting Alice thread")
        with NetSquidConnection("Alice") as alice:
            q1 = Qubit(alice)
            q2 = Qubit(alice)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        assert len(alice.active_qubits) == 0
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        with NetSquidConnection("Bob") as bob:
            q1 = Qubit(bob)
            q2 = Qubit(bob)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        assert len(bob.active_qubits) == 0
        logging.debug("End Bob thread")

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })


def test_measure():
    # logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            count = 0
            num = 100
            for _ in range(num):
                q = Qubit(alice)
                q.H()
                m = q.measure()
                alice.flush()
                count += m
            avg = count / num
            logging.info(avg)
            assert 0.4 <= avg <= 0.6

    run_applications({
        "Alice": run_alice,
    })


def test_measure_loop():
    # logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            num = 100

            def body(alice):
                q = Qubit(alice)
                q.H()
                q.measure(outcome_address='*i')

            alice.loop(body, end=num + 2, start=2, var_address='i')
            alice.flush()
            outcomes = alice.shared_memory[2:2 + num]
            avg = sum(outcomes) / num
            logging.info(f"Average: {avg}")
            assert 0.4 <= avg <= 0.6

    run_applications({
        "Alice": run_alice,
    })


def test_nested_loop():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            num = 10

            def outer_body(alice):
                def inner_body(alice):
                    q = Qubit(alice)
                    q.release()

                alice.loop(inner_body, num, var_address='i')
            alice.loop(outer_body, num, var_address='j')
            alice.flush()
            logging.info(alice.shared_memory[:10])
            assert alice.shared_memory[0] == num
            assert alice.shared_memory[1] == num

    run_applications({
        "Alice": run_alice,
    })


def test_create_epr():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            sleep(0.1)
            # Create entanglement
            alice.createEPR("Bob")[0]

    def run_bob():
        with NetSquidConnection("Bob") as bob:
            bob.recvEPR("Alice")[0]

    def post_function(backend):
        alice_state = backend._nodes["Alice"].qmemory._get_qubits(0)[0].qstate
        bob_state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate
        assert alice_state is bob_state
        expected_state = np.array(
            [[0.5, 0, 0, 0.5],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0.5, 0, 0, 0.5]])

        logging.info(f"state = {alice_state.dm}")
        assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_teleport():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            # Create a qubit
            q = Qubit(alice)
            q.H()

            # Create entanglement
            epr = alice.createEPR("Bob")[0]

            # Teleport
            q.cnot(epr)
            q.H()
            m1 = q.measure()
            m2 = epr.measure()
            logging.info(f"m1, m2 = {m1}, {m2}")

    def run_bob():
        with NetSquidConnection("Bob") as bob:
            bob.recvEPR("Alice")[0]

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
        m1, m2 = shared_memory_alice[0:2]
        expected_states = {
            (0, 0): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (0, 1): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (1, 0): np.array([[0.5, -0.5], [-0.5, 0.5]]),
            (1, 1): np.array([[0.5, -0.5], [-0.5, 0.5]]),
        }
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logging.info(f"state = {state}")
        assert np.all(np.isclose(expected_states[m1, m2], state))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    # test_two_nodes()
    # test_measure()
    # test_measure_loop()
    # test_nested_loop()
    # test_create_epr()
    test_teleport()
