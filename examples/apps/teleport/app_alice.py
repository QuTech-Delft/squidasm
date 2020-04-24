from netqasm.sdk import Qubit
from squidasm.sdk import NetSquidConnection, NetSquidSocket


def main(track_lines=True, log_subroutines_dir=None, phi=0., theta=0.):

    # Create a socket to send classical information
    socket = NetSquidSocket("alice", "bob")

    # Initialize the connection to the backend
    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_to="bob",
    )
    with alice:
        # Create a qubit to teleport
        q = Qubit(alice)
        # q = set_qubit_state(q, phi, theta)
        q.H()

        # Create EPR pairs
        epr = alice.createEPR("bob")[0]

        # Teleport
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()

        # To check states for debugging
        alice._release_qubits_on_exit = False

    # Send the correction information
    msg = str((int(m1), int(m2)))
    socket.send(msg)


if __name__ == "__main__":
    main()
