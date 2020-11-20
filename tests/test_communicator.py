import logging
import numpy as np

from netqasm.logging.glob import set_log_level, get_netqasm_logger
from netqasm.lang.parsing import parse_register
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.backend.network_stack import CREATE_FIELDS, OK_FIELDS
from netqasm.runtime.app_config import default_app_config

from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator

logger = get_netqasm_logger()


def test():
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE op h
# DEFINE q Q0
# DEFINE m M0
set q! 0
qalloc q!
init q!
op! q! // this is a comment
meas q! m!
bez m! EXIT
x q!
EXIT:
ret_reg m!
// this is also a comment
"""
    logger.info("Applications at Alice and Bob will submit the following subroutine to QDevice:")
    logger.info(subroutine)

    def run_alice():
        logger.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutines=[subroutine])
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutines=[subroutine])
        communicator.run(num_times=1)
        logger.debug("End Bob thread")

    def post_function(backend):
        for node_name in ["Alice", "Bob"]:
            shared_memory = get_shared_memory(node_name, key=0)
            outcome = shared_memory.get_register(parse_register("M0"))
            logger.info(f"m = {outcome}")
            assert outcome in set([0, 1])

    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob)
    ], use_app_config=False, post_function=post_function)


def test_meas_many():
    num_times = 100
    subroutine = f"""
# NETQASM 0.0
# APPID 0
# DEFINE ms @0
# DEFINE i R0
# DEFINE q Q0
# DEFINE m M0
array({num_times}) ms!
set i! 0
set q! 0
LOOP:
beq i! {num_times} EXIT
qalloc q!
init q!
h q!
meas q! m!
store m! ms![i!]
qfree q!
add i! i! 1
jmp LOOP
EXIT:
ret_reg i!
ret_arr ms!
// this is also a comment
"""
    logger.info("Applications at Alice will submit the following subroutine to QDevice:")
    logger.info(subroutine)

    def run_alice():
        logger.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutines=[subroutine])
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def post_function(backend):
        shared_memory = get_shared_memory("Alice", key=0)
        outcomes = shared_memory[0]
        i = shared_memory.get_register(parse_register("R0"))
        assert i == num_times
        assert len(outcomes) == num_times
        avg = sum(outcomes) / num_times
        logger.info(avg)
        assert 0.4 <= avg <= 0.6

    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False, post_function=post_function)


def test_teleport():
    subroutine_alice = f"""
# NETQASM 0.0
# APPID 0
# DEFINE q Q0
# DEFINE epr Q1
# DEFINE epr_address 0
# DEFINE entinfo 1
# DEFINE arg_address 2
set q! 0
array(1) @epr_address!
store 1 @epr_address![0]
array({OK_FIELDS}) @entinfo!
array({CREATE_FIELDS}) @arg_address!
qalloc q!
init q!
h q!
create_epr(1, 0) epr_address! arg_address! entinfo!
wait_all @entinfo![0:{OK_FIELDS}]
load epr! @epr_address![0]
cnot q! epr!
h q!
meas q! M0
meas epr! M1
qfree q!
qfree epr!
ret_reg M0
ret_reg M1
"""
    subroutine_0_bob = f"""
# NETQASM 0.0
# APPID 0
# DEFINE epr Q1
# DEFINE epr_address 0
# DEFINE entinfo 1
array(1) @epr_address!
store 0 @epr_address![0]
array({OK_FIELDS}) @entinfo!
recv_epr(0, 0) epr_address! entinfo!
wait_all @entinfo![0:{OK_FIELDS}]
"""

    def run_alice():
        logger.debug("Starting Alice thread")
        epr_socket = EPRSocket("Bob")
        communicator = SimpleCommunicator(
            "Alice",
            subroutines=[subroutine_alice],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        epr_socket = EPRSocket("Alice")
        communicator = SimpleCommunicator(
            "Bob",
            subroutines=[subroutine_0_bob],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        m1 = shared_memory_alice.get_register(parse_register("M0"))
        m2 = shared_memory_alice.get_register(parse_register("M1"))
        expected_states = {
            (0, 0): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (0, 1): np.array([[0.5, 0.5], [0.5, 0.5]]),
            (1, 0): np.array([[0.5, -0.5], [-0.5, 0.5]]),
            (1, 1): np.array([[0.5, -0.5], [-0.5, 0.5]]),
        }
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logger.info(f"m1 = {m1}, m2 = {m2}")
        logger.info(f"state = {state}")
        assert np.all(np.isclose(expected_states[m1, m2], state))

    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)


def test_set_create_args():
    subroutine_alice = f"""
# NETQASM 0.0
# APPID 0
# DEFINE q Q0
# DEFINE epr Q1
# DEFINE epr_address 0
# DEFINE entinfo 1
# DEFINE arg_address 2
// qubit address to use
array(1) @epr_address!
store 0 @epr_address![0]

// arguments for create epr
array({CREATE_FIELDS}) @arg_address!
store 0 @arg_address![0]  // type",
store 1 @arg_address![1]  // number",
store 0 @arg_address![2]  // minimum_fidelity",
store 0 @arg_address![3]  // time_unit",
store 0 @arg_address![4]  // max_time",
store 0 @arg_address![5]  // priority",
store 0 @arg_address![6]  // atomic",
store 0 @arg_address![7]  // consecutive",
store 0 @arg_address![8]  // random_basis_local",
store 0 @arg_address![9]  // random_basis_remote",
store 0 @arg_address![10] // probability_dist_local1",
store 0 @arg_address![11] // probability_dist_local2",
store 0 @arg_address![12] // probability_dist_remote1",
store 0 @arg_address![13] // probability_dist_remote2",
store 0 @arg_address![14] // rotation_X_local1",
store 0 @arg_address![15] // rotation_Y_local",
store 0 @arg_address![16] // rotation_X_local2",
store 0 @arg_address![17] // rotation_X_remote1",
store 0 @arg_address![18] // rotation_Y_remote",
store 0 @arg_address![19] // rotation_X_remote2",

// where to store the entanglement information
array({OK_FIELDS}) @entinfo!

// Do some gates to make the recv come first
set q! 1
qalloc q!
init q!
h q!

// create entanglement
create_epr(1, 0) epr_address! arg_address! entinfo!
wait_all @entinfo![0:{OK_FIELDS}]
"""
    subroutine_0_bob = f"""
# NETQASM 0.0
# APPID 0
# DEFINE epr Q1
# DEFINE epr_address 0
# DEFINE entinfo 1
array(1) @epr_address!
store 0 @epr_address![0]
array({OK_FIELDS}) @entinfo!
recv_epr(0, 0) epr_address! entinfo!
wait_all @entinfo![0:{OK_FIELDS}]
"""

    def run_alice():
        logger.debug("Starting Alice thread")
        epr_socket = EPRSocket("Bob")
        communicator = SimpleCommunicator(
            "Alice",
            subroutines=[subroutine_alice],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        epr_socket = EPRSocket("Alice")
        communicator = SimpleCommunicator(
            "Bob",
            subroutines=[subroutine_0_bob],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Bob thread")

    def post_function(backend):
        states = []
        for node_name in ["Alice", "Bob"]:
            executioner = backend._subroutine_handlers[node_name]._executioner
            physical_qubit = executioner._get_position_in_unit_module(app_id=0, address=0)
            state = backend._nodes[node_name].qmemory._get_qubits(physical_qubit)[0].qstate
            states.append(state)
        # alice_physical_qubit = backend._subroutine_handlers["Alice"]._executioner._get_position(0, 0)
        # bob_physical_qubit = backend._subroutine_handlers["Bob"]._executioner._get_position(0, 0)
        # alice_state = backend._nodes["Alice"].qmemory._get_qubits(alice_physical_qubit)[0].qstate
        # bob_state = backend._nodes["Bob"].qmemory._get_qubits(bob_physical_qubit)[0].qstate
        alice_state, bob_state = states
        assert alice_state is bob_state
        expected_state = np.array(
            [[0.5, 0, 0, 0.5],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0.5, 0, 0, 0.5]])

        assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)


def test_multiple_pairs():
    subroutine_alice = f"""
# NETQASM 0.0
# APPID 0
# DEFINE q Q0
# DEFINE epr Q1
# DEFINE epr_address 0
# DEFINE entinfo 1
# DEFINE arg_address 2
// qubit address to use
array(2) @epr_address!
store 0 @epr_address![0]
store 1 @epr_address![1]

// arguments for create epr
array({CREATE_FIELDS}) @arg_address!
store 0 @arg_address![0]  // type",
store 2 @arg_address![1]  // number",
store 0 @arg_address![2]  // minimum_fidelity",
store 0 @arg_address![3]  // time_unit",
store 0 @arg_address![4]  // max_time",
store 0 @arg_address![5]  // priority",
store 0 @arg_address![6]  // atomic",
store 0 @arg_address![7]  // consecutive",
store 0 @arg_address![8]  // random_basis_local",
store 0 @arg_address![9]  // random_basis_remote",
store 0 @arg_address![10] // probability_dist_local1",
store 0 @arg_address![11] // probability_dist_local2",
store 0 @arg_address![12] // probability_dist_remote1",
store 0 @arg_address![13] // probability_dist_remote2",
store 0 @arg_address![14] // rotation_X_local1",
store 0 @arg_address![15] // rotation_Y_local",
store 0 @arg_address![16] // rotation_X_local2",
store 0 @arg_address![17] // rotation_X_remote1",
store 0 @arg_address![18] // rotation_Y_remote",
store 0 @arg_address![19] // rotation_X_remote2",

// where to store the entanglement information
array({2 * OK_FIELDS}) @entinfo!

// Wait a little to make the recv come first
set q! 2
qalloc q!
init q!
h q!

// create entanglement
create_epr(1, 0) epr_address! arg_address! entinfo!
wait_all @entinfo![0:{2 * OK_FIELDS}]
"""
    subroutine_0_bob = f"""
# NETQASM 0.0
# APPID 0
# DEFINE epr_address 0
# DEFINE entinfo 1
array(2) @epr_address!
store 0 @epr_address![0]
store 1 @epr_address![1]
array({2 * OK_FIELDS}) @entinfo!
recv_epr(0, 0) epr_address! entinfo!
wait_all @entinfo![0:{2 * OK_FIELDS}]
"""

    def run_alice():
        logger.debug("Starting Alice thread")
        epr_socket = EPRSocket("Bob")
        communicator = SimpleCommunicator(
            "Alice",
            subroutines=[subroutine_alice],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        epr_socket = EPRSocket("Alice")
        communicator = SimpleCommunicator(
            "Bob",
            subroutines=[subroutine_0_bob],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Bob thread")

    def post_function(backend):
        for i in range(2):
            states = []
            for node_name in ["Alice", "Bob"]:
                executioner = backend._subroutine_handlers[node_name]._executioner
                physical_qubit = executioner._get_position_in_unit_module(app_id=0, address=0)
                state = backend._nodes[node_name].qmemory._get_qubits(physical_qubit)[0].qstate
                states.append(state)
            # alice_physical_qubit = backend._subroutine_handlers["Alice"]._executioner._get_position(0, i)
            # bob_physical_qubit = backend._subroutine_handlers["Bob"]._executioner._get_position(0, i)
            # alice_state = backend._nodes["Alice"].qmemory._get_qubits(alice_physical_qubit)[0].qstate
            # bob_state = backend._nodes["Bob"].qmemory._get_qubits(bob_physical_qubit)[0].qstate
            alice_state, bob_state = states
            assert alice_state is bob_state
            expected_state = np.array(
                [[0.5, 0, 0, 0.5],
                 [0, 0, 0, 0],
                 [0, 0, 0, 0],
                 [0.5, 0, 0, 0.5]])

            assert np.all(np.isclose(expected_state, alice_state.dm))

    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)


def test_make_ghz():
    subroutine_alice = f"""
# NETQASM 0.0
# APPID 0
// qubit address to use
# DEFINE q Q0
# DEFINE epr_address 0
# DEFINE entinfo 1
# DEFINE arg_address 2
array(2) @epr_address!
store 0 @epr_address![0]
store 1 @epr_address![1]

// arguments for create epr
array({CREATE_FIELDS}) @arg_address!
store 0 @arg_address![0]  // type",
store 2 @arg_address![1]  // number",
store 0 @arg_address![2]  // minimum_fidelity",
store 0 @arg_address![3]  // time_unit",
store 0 @arg_address![4]  // max_time",
store 0 @arg_address![5]  // priority",
store 0 @arg_address![6]  // atomic",
store 0 @arg_address![7]  // consecutive",
store 0 @arg_address![8]  // random_basis_local",
store 0 @arg_address![9]  // random_basis_remote",
store 0 @arg_address![10] // probability_dist_local1",
store 0 @arg_address![11] // probability_dist_local2",
store 0 @arg_address![12] // probability_dist_remote1",
store 0 @arg_address![13] // probability_dist_remote2",
store 0 @arg_address![14] // rotation_X_local1",
store 0 @arg_address![15] // rotation_Y_local",
store 0 @arg_address![16] // rotation_X_local2",
store 0 @arg_address![17] // rotation_X_remote1",
store 0 @arg_address![18] // rotation_Y_remote",
store 0 @arg_address![19] // rotation_X_remote2",

// where to store the entanglement information
array({2 * OK_FIELDS}) @entinfo!

// Wait a little to make the recv come first
set q! 2
qalloc q!
init q!
h q!

// create entanglement
create_epr(1, 0) epr_address! arg_address! entinfo!
wait_all @entinfo![0:{2 * OK_FIELDS}]
load Q1 @epr_address![0]
load Q2 @epr_address![1]
cnot Q1 Q2
meas Q2 M0
qfree Q2
ret_reg M0
"""
    subroutine_0_bob = f"""
# NETQASM 0.0
# APPID 0
# DEFINE epr_address 0
# DEFINE entinfo 1
array(2) @epr_address!
store 0 @epr_address![0]
store 1 @epr_address![1]
array({2 * OK_FIELDS}) @entinfo!
recv_epr(0, 0) epr_address! entinfo!
wait_all @entinfo![0:{2 * OK_FIELDS}]
"""

    def run_alice():
        logger.debug("Starting Alice thread")
        epr_socket = EPRSocket("Bob")
        communicator = SimpleCommunicator(
            "Alice",
            subroutines=[subroutine_alice],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def run_bob():
        logger.debug("Starting Bob thread")
        epr_socket = EPRSocket("Alice")
        communicator = SimpleCommunicator(
            "Bob",
            subroutines=[subroutine_0_bob],
            epr_sockets=[epr_socket],
        )
        communicator.run(num_times=1)
        logger.debug("End Bob thread")

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        m = shared_memory_alice.get_register(parse_register("M0"))
        logger.info(f"m = {m}")
        states = []
        for pos, node in zip([0, 0, 1], ["Alice", "Bob", "Bob"]):
            executioner = backend._subroutine_handlers[node]._executioner
            physical_pos = executioner._get_position_in_unit_module(app_id=0, address=pos)
            state = backend._nodes[node].qmemory._get_qubits(physical_pos)[0].qstate
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

        logger.info(states[0].dm)

        assert np.all(np.isclose(expected_state, states[0].dm))

    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)


if __name__ == '__main__':
    set_log_level(logging.INFO)
    test()
    test_meas_many()
    test_teleport()
    test_set_create_args()
    test_multiple_pairs()
    test_make_ghz()
