import logging

from netqasm.sdk.shared_memory import get_shared_memory
from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator


def test():
    logging.basicConfig(level=logging.DEBUG)
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE op h
# DEFINE q q0
qalloc q!
init q!
op! q! // this is a comment
meas q! m
beq m 0 EXIT
x q!
EXIT:
// this is also a comment
"""
    print("Applications at Alice and Bob will submit the following subroutine to QDevice:")
    print(subroutine)
    print()

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

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })
    for node in ["Alice", "Bob"]:
        shared_memory = get_shared_memory(node, key=0)
        print(shared_memory[:10])
        assert shared_memory[0] in set([0, 1])


def test_meas_many():
    logging.basicConfig(level=logging.DEBUG)
    num_times = 100
    subroutine = f"""
# NETQASM 0.0
# APPID 0
array({num_times}) ms
store i 0
LOOP:
beq i {num_times} EXIT
qalloc q
init q
h q
meas q ms[]
qfree q
add i i 1
beq 0 0 LOOP
EXIT:
// this is also a comment
"""
    print("Applications at Alice will submit the following subroutine to QDevice:")
    print(subroutine)
    print()

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    run_applications({
        "Alice": run_alice,
    })

    shared_memory = get_shared_memory("Alice", key=0)
    outcomes = shared_memory[0]
    i = shared_memory[1]
    assert i == num_times
    assert len(outcomes) == num_times
    avg = sum(outcomes) / num_times
    print(avg)
    assert 0.4 <= avg <= 0.6


if __name__ == '__main__':
    test()
    test_meas_many()
