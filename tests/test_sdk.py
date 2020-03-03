import logging

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
            print(avg)
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
            print(f"Average: {avg}")
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
            print(alice.shared_memory[:10])
            assert alice.shared_memory[0] == num
            assert alice.shared_memory[1] == num

    run_applications({
        "Alice": run_alice,
    })


if __name__ == '__main__':
    test_two_nodes()
    test_measure()
    test_measure_loop()
    test_nested_loop()
