import os
import logging
import numpy as np

from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator


def get_subroutines():
    subroutines = []
    for filename in ['subroutine_alice.nqasm', 'subroutine_bob.nqasm']:
        dir_path = os.path.dirname(__file__)
        file_path = os.path.join(dir_path, filename)
        with open(file_path, 'r') as f:
            subroutine = f.read()
        subroutines.append(subroutine)
    return subroutines


def main():
    logging.basicConfig(level=logging.DEBUG)

    subroutine_alice, subroutine_bob = get_subroutines()

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine_alice)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine_bob)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        m1, m2 = shared_memory_alice[3:5]
        expected_states = {
            (0, 0): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (0, 1): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (1, 0): np.array([[0.5, -0.5], [-0.5, 0.5]]),
            (1, 1): np.array([[0.5, -0.5], [-0.5, 0.5]]),
        }
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logging.info(f"m1 = {m1}, m2 = {m2}")
        logging.info(f"state = {state}")
        assert np.all(np.isclose(expected_states[m1, m2], state))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    main()
