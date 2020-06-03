import numpy as np

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection

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


def main(track_lines=True, log_subroutines_dir=None, app_dir=None):
    socket = Socket("bob", "alice", comm_log_dir=log_subroutines_dir, track_lines=track_lines, app_dir=app_dir)
    epr_socket = EPRSocket("alice")

    num_qubits = 4

    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        app_dir=app_dir,
        epr_sockets=[epr_socket],
        max_qubits=num_qubits
    )

    with bob:
        # Receive qubits q0 to q3 from Alice by teleportation.
        q = [None] * num_qubits
        for i in range(num_qubits):
            q[i] = recv_teleported_state(epr_socket)

        # Apply CPHASE gates between neighbouring nodes.
        # (See cluster state in the README.)
        for i in range(num_qubits - 1):
            q[i].cphase(q[i + 1])
        q[0].cphase(q[2])

        # Receive from Alice the angle to measure q1 in.
        delta1 = recv_meas_cmd(socket)
        s1 = measXY(q[1], delta1)
        bob.flush()
        send_meas_outcome(socket, s1)

        # Receive from Alice the angle to measure q2 in.
        delta2 = recv_meas_cmd(socket)
        s2 = measXY(q[2], delta2)
        bob.flush()
        send_meas_outcome(socket, s2)

        # Measure the output qubits (q0 and q3) in the Y-basis.
        m0 = measXY(q[0], np.pi / 2)
        m1 = measXY(q[3], np.pi / 2)
        bob.flush()

        # Send the measurement outcomes to Alice.
        send_meas_outcome(socket, m0)
        send_meas_outcome(socket, m1)
