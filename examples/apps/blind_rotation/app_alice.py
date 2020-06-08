import random
import numpy as np

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from examples.lib.bqc import teleport_state, send_meas_cmd, recv_meas_outcome

logger = get_netqasm_logger()


def main(
        track_lines=True,
        log_subroutines_dir=None,
        app_dir=None,
        lib_dirs=[],
        num_iter=3,
        theta=None,
        phi=None,
        r=None):

    socket = Socket("alice", "bob", comm_log_dir=log_subroutines_dir, track_lines=track_lines, app_dir=app_dir, lib_dirs=lib_dirs)
    epr_socket = EPRSocket("bob")

    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        app_dir=app_dir,
        lib_dirs=lib_dirs,
        epr_sockets=[epr_socket],
    )

    num_qubits = num_iter + 1

    if theta is None:
        theta = [0 for _ in range(num_qubits)]
    if phi is None:
        phi = [random.uniform(0, 2 * np.pi) for _ in range(num_iter)]
    if r is None:
        r = [0 for _ in range(num_iter)]

    with alice:
        # Teleport states q[0] to q[num_qubits - 1] to Bob.
        # The resulting state q[i] might have a phase `pi`,
        # depending on outcome m[i].
        m = [None] * num_qubits
        for i in range(num_qubits):
            m[i] = teleport_state(epr_socket, theta[i])
        alice.flush()

        # Convert outcomes to integers to use them in calculations below.
        m = [int(m[i]) for i in range(num_qubits)]

        # delta[i] will hold the actual measurement angle sent to Bob.
        delta = [None] * num_iter
        # s[i] will hold the measurement outcome for qubit q[i].
        s = [None] * num_iter

        # For r and s, temporarily add two 0s at the end,
        # so that we can use indices -1 and -2 for convenience.
        s.extend([0, 0])
        r.extend([0, 0])

        # Main loop. For each iteration i, we let Bob measure q[i].
        # We want to measure with angle phi[i], but initial phases
        # (m[i] and theta[i]), as well as previous measurement outcomes s[j]
        # and secret key bits r[j] are required to be compensated for.
        # The actual angle we send to Bob is then called delta[i].
        for i in range(num_iter):
            delta[i] = pow(-1, s[i-1] ^ r[i-1]) * phi[i]
            delta[i] += (s[i-2] ^ r[i-2]) * np.pi
            delta[i] += r[i] * np.pi
            # we have q[i] = Rz(m[i]*pi + theta[i]), compensate for this:
            delta[i] -= theta[i]
            delta[i] -= m[i] * np.pi

            send_meas_cmd(socket, delta[i])
            s[i] = recv_meas_outcome(socket)

        # remove last 2 temporary 0s
        s = s[0:num_iter]
        r = r[0:num_iter]

        return {
            "delta": delta,
            "s": s,
            "m": m,
            "theta": theta,
            "phi": phi,
            "r": r,
        }
