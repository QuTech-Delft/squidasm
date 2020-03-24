import logging

from netqasm.sdk import Qubit
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications


def main():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            # Create a qubit
            q = Qubit(alice)

            # Perform a Hadmard gate
            q.H()

            # Measure the qubit
            m = q.measure()

            print(m)

    run_applications({
        "Alice": run_alice,
    })


if __name__ == '__main__':
    main()
