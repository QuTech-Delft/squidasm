from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket, ThreadSocket, Qubit
from netqasm.sdk.toolbox import set_qubit_state
from squidasm.sdk import NetSquidConnection

ALLOWED_TARGET_VALUES = ["0", "1", "+", "-", "i", "-i"]


def main(track_lines=True, log_subroutines_dir=None, phi=0.0, theta=0.0):
    _logger = get_netqasm_logger()

    # socket for creating an EPR pair with Alice
    alice_epr = EPRSocket("alice")

    # socket for communicating classical messages with Alice
    class_socket = ThreadSocket("bob", "alice", comm_log_dir=log_subroutines_dir)

    # connect to the back-end
    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=[alice_epr]
    )

    with bob:
        # create one EPR pair with Alice
        epr_list = alice_epr.recv(1)
        epr = epr_list[0]

        # initialize target qubit of the distributed CNOT
        target_qubit = Qubit(bob)
        set_qubit_state(target_qubit, phi, theta)

        # let back-end execute the quantum operations above
        bob.flush()

        # wait for Alice's measurement outcome
        m = class_socket.recv()

        # if outcome = 1, apply an X gate on the local EPR half
        if m == "1":
            _logger.debug("applying X")
            epr.X()

        # At this point, `epr` is entangled with the control qubit on Alice's side.
        # Use `epr` as the control of a local CNOT on the target qubit.
        epr.cnot(target_qubit)

        # let back-end execute the above quantum operations
        bob.flush()

        # undo the entanglement between `epr` and the control qubit on Alice's side
        epr.H()
        epr_meas = epr.measure()
        bob.flush()

        # Alice will do a controlled-Z based on the outcome to undo the entanglement
        class_socket.send(str(epr_meas))

    return {
        'epr_meas': int(epr_meas)
    }

    