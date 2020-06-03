from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from squidasm.sim_util import get_qubit_state

logger = get_netqasm_logger()


def measXY(q, angle):
    """Measure qubit `q` in the XY-plane rotated by `angle`.
    Note: we use the convention that we rotate by +`angle` (not -`angle`).
    """
    q.rot_Z(angle=angle)
    q.H()
    return q.measure()


def recv_teleported_state(epr_socket):
    """Let Alice teleport a state to Bob.
    She will do a suitable measurement on her side.
    """
    return epr_socket.recv()[0]


def recv_meas_cmd(socket):
    """Receive the angle to measure the next qubit in."""
    return float(socket.recv())


def send_meas_outcome(socket, outcome):
    """Send the outcome (0 or 1) of the latest measurement to Alice."""
    socket.send(str(outcome))


def main(track_lines=True, log_subroutines_dir=None, app_dir=None, num_iter=3):
    socket = Socket("bob", "alice", comm_log_dir=log_subroutines_dir, track_lines=track_lines, app_dir=app_dir)
    epr_socket = EPRSocket("alice")

    num_qubits = num_iter + 1

    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        app_dir=app_dir,
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
