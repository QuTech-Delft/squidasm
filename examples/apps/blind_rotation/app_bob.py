from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from squidasm.sim_util import get_qubit_state
from examples.lib.bqc import measXY, recv_teleported_state, recv_meas_cmd, send_meas_outcome

logger = get_netqasm_logger()


def main(log_config=None, num_iter=3):
    socket = Socket("bob", "alice", log_config=log_config)
    epr_socket = EPRSocket("alice")

    num_qubits = num_iter + 1

    bob = NetSquidConnection(
        "bob",
        log_config=log_config,
        epr_sockets=[epr_socket],
        max_qubits=num_qubits
    )

    with bob:
        # Receive qubits q[0] to q[num_qubits - 1] from Alice by teleportation.
        q = [None] * num_qubits
        for i in range(num_qubits):
            q[i] = recv_teleported_state(epr_socket)

        # Apply a CPHASE gate between every pair of consecutive qubits.
        for i in range(num_qubits - 1):
            q[i].cphase(q[i+1])

        # Main loop. Receive from Alice the angle to measure q[i] in.
        for i in range(num_iter):
            angle = recv_meas_cmd(socket)
            s = measXY(q[i], angle)
            bob.flush()
            send_meas_outcome(socket, s)

        # The output of the computation is in the last qubit.
        dm = get_qubit_state(q[num_qubits - 1])
        return {
            "output_state": dm.tolist()
        }