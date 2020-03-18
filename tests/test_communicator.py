import logging
import numpy as np

from netqasm.sdk.shared_memory import get_shared_memory
from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator


def test():
    # logging.basicConfig(level=logging.DEBUG)
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
    logging.info("Applications at Alice and Bob will submit the following subroutine to QDevice:")
    logging.info(subroutine)

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
            logging.info(shared_memory[:10])
            assert shared_memory[0] in set([0, 1])

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_meas_many():
    # logging.basicConfig(level=logging.DEBUG)
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
    logging.info("Applications at Alice will submit the following subroutine to QDevice:")
    logging.info(subroutine)

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def post_function(backend):
        shared_memory = get_shared_memory("Alice", key=0)
        outcomes = shared_memory[0]
        i = shared_memory[1]
        assert i == num_times
        assert len(outcomes) == num_times
        avg = sum(outcomes) / num_times
        logging.info(avg)
        assert 0.4 <= avg <= 0.6

    run_applications({
        "Alice": run_alice,
    }, post_function=post_function)


def test_teleport():
    # logging.basicConfig(level=logging.DEBUG)
    subroutine_alice = """
# NETQASM 0.0
# APPID 0
array(1) epr_address
store epr_address[0] 1
array(1) entinfo
array(20) arg_address
qalloc q
init q
h q
create_epr(1, 0) epr_address arg_address entinfo
wait entinfo
cnot q epr_address[0]
h q
meas q m1
meas epr_address[0] m2
qfree q
qfree epr_address[0]
"""
    subroutine_0_bob = """
# NETQASM 0.0
# APPID 0
array(1) epr_address
store epr_address[0] 0
array(1) entinfo
recv_epr(0, 0) epr_address entinfo
wait entinfo
"""

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine_alice)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine_0_bob)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
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


def test_set_create_args():
    # logging.basicConfig(level=logging.DEBUG)
    subroutine_alice = """
# NETQASM 0.0
# APPID 0
// qubit address to use
array(1) epr_address
store epr_address[0] 0

// arguments for create epr
array(20) arg_address
store arg_address[0] 0 // type",
store arg_address[1] 1 // number",
store arg_address[2] 0 // minimum_fidelity",
store arg_address[3] 0 // time_unit",
store arg_address[4] 0 // max_time",
store arg_address[5] 0 // priority",
store arg_address[6] 0 // atomic",
store arg_address[7] 0 // consecutive",
store arg_address[8] 0 // random_basis_local",
store arg_address[9] 0 // random_basis_remote",
store arg_address[10] 0 // probability_dist_local1",
store arg_address[11] 0 // probability_dist_local2",
store arg_address[12] 0 // probability_dist_remote1",
store arg_address[13] 0 // probability_dist_remote2",
store arg_address[14] 0 // rotation_X_local1",
store arg_address[15] 0 // rotation_Y_local",
store arg_address[16] 0 // rotation_X_local2",
store arg_address[17] 0 // rotation_X_remote1",
store arg_address[18] 0 // rotation_Y_remote",
store arg_address[19] 0 // rotation_X_remote2",

// where to store the entanglement information
array(1) entinfo

// Wait a little to make the recv come first
wait 1

// create entanglement
create_epr(1, 0) epr_address arg_address entinfo
wait entinfo
"""
    subroutine_0_bob = """
# NETQASM 0.0
# APPID 0
array(1) epr_address
store epr_address[0] 0
array(1) entinfo
recv_epr(0, 0) epr_address entinfo
wait entinfo
"""

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine_alice)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine_0_bob)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
        alice_state = backend._nodes["Alice"].qmemory._get_qubits(0)[0].qstate
        bob_state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate
        assert alice_state is bob_state
        expected_state = np.array(
            [[0.5, 0, 0, 0.5],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0.5, 0, 0, 0.5]])

        assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_multiple_pairs():
    # logging.basicConfig(level=logging.DEBUG)
    subroutine_alice = """
# NETQASM 0.0
# APPID 0
// qubit address to use
array(2) epr_address
store epr_address[0] 0
store epr_address[1] 1

// arguments for create epr
array(20) arg_address
store arg_address[0] 0 // type",
store arg_address[1] 2 // number",
store arg_address[2] 0 // minimum_fidelity",
store arg_address[3] 0 // time_unit",
store arg_address[4] 0 // max_time",
store arg_address[5] 0 // priority",
store arg_address[6] 0 // atomic",
store arg_address[7] 0 // consecutive",
store arg_address[8] 0 // random_basis_local",
store arg_address[9] 0 // random_basis_remote",
store arg_address[10] 0 // probability_dist_local1",
store arg_address[11] 0 // probability_dist_local2",
store arg_address[12] 0 // probability_dist_remote1",
store arg_address[13] 0 // probability_dist_remote2",
store arg_address[14] 0 // rotation_X_local1",
store arg_address[15] 0 // rotation_Y_local",
store arg_address[16] 0 // rotation_X_local2",
store arg_address[17] 0 // rotation_X_remote1",
store arg_address[18] 0 // rotation_Y_remote",
store arg_address[19] 0 // rotation_X_remote2",

// where to store the entanglement information
array(2) entinfo

// Wait a little to make the recv come first
wait 1

// create entanglement
create_epr(1, 0) epr_address arg_address entinfo
wait entinfo
"""
    subroutine_0_bob = """
# NETQASM 0.0
# APPID 0
array(2) epr_address
store epr_address[0] 0
store epr_address[1] 1
array(2) entinfo
recv_epr(0, 0) epr_address entinfo
wait entinfo
"""

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine_alice)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine_0_bob)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
        for i in range(2):
            alice_state = backend._nodes["Alice"].qmemory._get_qubits(i)[0].qstate
            bob_state = backend._nodes["Bob"].qmemory._get_qubits(i)[0].qstate
            assert alice_state is bob_state
            expected_state = np.array(
                [[0.5, 0, 0, 0.5],
                 [0, 0, 0, 0],
                 [0, 0, 0, 0],
                 [0.5, 0, 0, 0.5]])

            assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


def test_make_ghz():
    # logging.basicConfig(level=logging.DEBUG)
    subroutine_alice = """
# NETQASM 0.0
# APPID 0
// qubit address to use
array(2) epr_address
store epr_address[0] 0
store epr_address[1] 1

// arguments for create epr
array(20) arg_address
store arg_address[0] 0 // type",
store arg_address[1] 2 // number",
store arg_address[2] 0 // minimum_fidelity",
store arg_address[3] 0 // time_unit",
store arg_address[4] 0 // max_time",
store arg_address[5] 0 // priority",
store arg_address[6] 0 // atomic",
store arg_address[7] 0 // consecutive",
store arg_address[8] 0 // random_basis_local",
store arg_address[9] 0 // random_basis_remote",
store arg_address[10] 0 // probability_dist_local1",
store arg_address[11] 0 // probability_dist_local2",
store arg_address[12] 0 // probability_dist_remote1",
store arg_address[13] 0 // probability_dist_remote2",
store arg_address[14] 0 // rotation_X_local1",
store arg_address[15] 0 // rotation_Y_local",
store arg_address[16] 0 // rotation_X_local2",
store arg_address[17] 0 // rotation_X_remote1",
store arg_address[18] 0 // rotation_Y_remote",
store arg_address[19] 0 // rotation_X_remote2",

// where to store the entanglement information
array(2) entinfo

// Wait a little to make the recv come first
wait 1

// create entanglement
create_epr(1, 0) epr_address arg_address entinfo
wait entinfo
cnot epr_address[0] epr_address[1]
meas epr_address[1] m
qfree epr_address[1]
"""
    subroutine_0_bob = """
# NETQASM 0.0
# APPID 0
array(2) epr_address
store epr_address[0] 0
store epr_address[1] 1
array(2) entinfo
recv_epr(0, 0) epr_address entinfo
wait entinfo
"""

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine_alice)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine_0_bob)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
        m = shared_memory_alice[3]
        states = []
        for pos, node in zip([0, 0, 1], ["Alice", "Bob", "Bob"]):
            state = backend._nodes[node].qmemory._get_qubits(pos)[0].qstate
            states.append(state)
        for i, state1 in enumerate(states):
            for j in range(i, len(states)):
                state2 = states[j]
                assert state1 is state2
        if m == 0:
            expected_state = np.zeros((8, 8))
            expected_state[0, 0] = 0.5
            expected_state[0, 7] = 0.5
            expected_state[7, 0] = 0.5
            expected_state[7, 7] = 0.5
        else:
            expected_state = np.zeros((8, 8))
            expected_state[1, 1] = 0.5
            expected_state[1, 6] = 0.5
            expected_state[6, 1] = 0.5
            expected_state[6, 6] = 0.5

        logging.info(states[0].dm)

        assert np.all(np.isclose(expected_state, states[0].dm))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    test()
    test_meas_many()
    test_teleport()
    test_set_create_args()
    test_multiple_pairs()
    test_make_ghz()
