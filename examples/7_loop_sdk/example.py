import logging

from netqasm.sdk import Qubit
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications


def main():
    logging.basicConfig(level=logging.DEBUG)

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


if __name__ == '__main__':
    main()
