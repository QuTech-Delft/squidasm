import random
import pytest
import logging
import numpy as np
from time import sleep

from netqasm.sdk import Qubit
from netqasm.logging import set_log_level, get_netqasm_logger
from netqasm.parsing import parse_register
from squidasm.sdk import NetSquidConnection, NetSquidSocket
from squidasm.run import run_applications

logger = get_netqasm_logger()


def test_two_nodes():

    def run_alice():
        logger.debug("Starting Alice thread")
        with NetSquidConnection("Alice") as alice:
            q1 = Qubit(alice)
            q2 = Qubit(alice)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        assert len(alice.active_qubits) == 0
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        with NetSquidConnection("Bob") as bob:
            q1 = Qubit(bob)
            q2 = Qubit(bob)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        assert len(bob.active_qubits) == 0
        logger.debug("End Bob thread")

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })


def test_measure():

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
            logger.info(avg)
            assert 0.4 <= avg <= 0.6

    run_applications({
        "Alice": run_alice,
    })


def test_measure_if_conn():
    def run_alice():
        num = 10
        with NetSquidConnection("Alice") as alice:
            for _ in range(num):
                q = Qubit(alice)
                q.H()
                m = q.measure(inplace=True)

                def body(alice):
                    q.X()

                alice.if_eq(m, 1, body)
                zero = q.measure()
                alice.flush()
                assert zero == 0

    run_applications({
        "Alice": run_alice,
    })


def test_measure_if_future():
    def run_alice():
        num = 10
        with NetSquidConnection("Alice") as alice:
            for _ in range(num):
                q = Qubit(alice)
                q.H()
                m = q.measure(inplace=True)
                with m.if_eq(1):
                    q.X()

                zero = q.measure()
                alice.flush()
                assert zero == 0

    run_applications({
        "Alice": run_alice,
    })


# TODO
@pytest.mark.skip(reason='Need to fix bug with loop')
def test_new_array():
    def run_alice():
        num = 10
        init_values = [random.randint(0, 1) for _ in range(num)]
        loop_register = "R0"

        with NetSquidConnection("Alice") as alice:
            array = alice.new_array(init_values=init_values)
            outcomes = alice.new_array(length=num)

            def body(alice):
                q = Qubit(alice)
                with array.get_future_index(loop_register).if_eq(1):
                    q.X()
                q.measure(array=outcomes, index=loop_register)

            alice.loop(body, stop=num, loop_register=loop_register)
        outcomes = list(outcomes)
        logger.debug(f"outcomes: {outcomes}")
        logger.debug(f"init_values: {init_values}")
        assert outcomes == init_values

    run_applications({
        "Alice": run_alice,
    })


# TODO
@pytest.mark.skip(reason='not working yet')
def test_post_epr():

    num = 2

    def run_alice():
        with NetSquidConnection("Alice") as alice:

            outcomes = alice.new_array(num)

            def post_create(conn, q, pair):
                q.H()
                outcome = outcomes.get_future_index(pair)
                q.measure(outcome)

            alice.createEPR("Bob", number=num, post_routine=post_create)

        print(list(outcomes))

    def run_bob():
        with NetSquidConnection("Bob") as bob:

            outcomes = bob.new_array(num)

            def post_recv(conn, q, pair):
                q.H()
                outcome = outcomes.get_future_index(pair)
                q.measure(outcome)

            bob.recvEPR("Bob", number=num, post_routine=post_recv)

        print(list(outcomes))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })


def test_measure_loop():

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            num = 100

            outcomes = alice.new_array(100)

            def body(alice):
                q = Qubit(alice)
                q.H()
                q.measure(future=outcomes.get_future_index("R0"))

            alice.loop(body, stop=num, loop_register="R0")
            alice.flush()
            assert len(outcomes) == num
            avg = sum(outcomes) / num
            logger.info(f"Average: {avg}")
            assert 0.4 <= avg <= 0.6

    run_applications({
        "Alice": run_alice,
    })


def test_nested_loop():
    inner_num = 10
    outer_num = 8
    inner_reg = "R0"
    outer_reg = "R1"

    def run_alice():
        with NetSquidConnection("Alice") as alice:

            def outer_body(alice):
                def inner_body(alice):
                    q = Qubit(alice)
                    q.release()

                alice.loop(inner_body, inner_num, loop_register=inner_reg)
            alice.loop(outer_body, outer_num, loop_register=outer_reg)

    def post_function(backend):
        executioner = backend._subroutine_handlers["Alice"]._executioner
        assert executioner._get_register(app_id=0, register=parse_register(inner_reg)) == inner_num
        assert executioner._get_register(app_id=0, register=parse_register(outer_reg)) == outer_num

    run_applications({
        "Alice": run_alice,
    }, post_function=post_function)


def test_create_epr():

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            # Wait a little to Bob has installed rule to recv
            sleep(0.1)

            # Create entanglement
            alice.createEPR("Bob")[0]

    def run_bob():
        with NetSquidConnection("Bob") as bob:
            bob.recvEPR("Alice")

    def post_function(backend):
        alice_state = backend._nodes["Alice"].qmemory._get_qubits(0)[0].qstate
        bob_state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate
        assert alice_state is bob_state
        expected_state = np.array(
            [[0.5, 0, 0, 0.5],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0.5, 0, 0, 0.5]])

        logger.info(f"state = {alice_state.dm}")
        assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_teleport_without_corrections():
    outcomes = []

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            # Wait a little to Bob has installed rule to recv
            sleep(0.1)

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
            outcomes.append(m1)
            outcomes.append(m2)

    def run_bob():
        with NetSquidConnection("Bob") as bob:
            bob.recvEPR("Alice")

    def post_function(backend):
        m1, m2 = outcomes
        logger.info(f"m1, m2 = {m1}, {m2}")
        expected_states = {
            (0, 0): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (0, 1): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (1, 0): np.array([[0.5, -0.5], [-0.5, 0.5]]),
            (1, 1): np.array([[0.5, -0.5], [-0.5, 0.5]]),
        }
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logger.info(f"state = {state}")
        expected = expected_states[m1, m2]
        logger.info(f"expected = {expected}")
        assert np.all(np.isclose(expected, state))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_teleport():
    def run_alice():
        socket = NetSquidSocket("Alice", "Bob")
        with NetSquidConnection("Alice") as alice:
            # Wait a little to Bob has installed rule to recv
            sleep(0.1)

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

        logger.info(f"m1, m2 = {m1}, {m2}")

        # Send the correction information
        msg = str((int(m1), int(m2)))
        socket.send(msg)

    def run_bob():
        socket = NetSquidSocket("Bob", "Alice")
        with NetSquidConnection("Bob") as bob:
            epr = bob.recvEPR("Alice")[0]
            bob.flush()

            # Get the corrections
            msg = socket.recv()
            logger.info(f"Bob got corrections: {msg}")
            m1, m2 = eval(msg)
            if m2 == 1:
                epr.X()
            if m1 == 1:
                epr.Z()

    def post_function(backend):
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logger.info(f"state = {state}")
        expected = np.array([[0.5, 0.5], [0.5, 0.5]])
        logger.info(f"expected = {expected}")
        assert np.all(np.isclose(expected, state))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    set_log_level(logging.WARNING)
    test_two_nodes()
    test_measure()
    test_measure_if_conn()
    test_measure_if_future()
    # test_new_array()
    # test_post_epr()
    test_measure_loop()
    test_nested_loop()
    test_create_epr()
    test_teleport_without_corrections()
    test_teleport()
