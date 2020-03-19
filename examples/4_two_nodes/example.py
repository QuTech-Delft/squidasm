import os
import logging

from netqasm.sdk.shared_memory import get_shared_memory
from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator


def get_subroutine():
    dir_path = os.path.dirname(__file__)
    file_path = os.path.join(dir_path, 'subroutine.nqasm')
    with open(file_path, 'r') as f:
        subroutine = f.read()
    return subroutine


def main():
    logging.basicConfig(level=logging.DEBUG)

    subroutine = get_subroutine()

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        for node_name in ["Alice", "Bob"]:
            shared_memory = get_shared_memory(node_name, key=0)
            print(f"Outcome in shared memory: {shared_memory[0]}")
            assert shared_memory[0] in set([0, 1])

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    main()
