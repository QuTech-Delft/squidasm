from netqasm.logging import get_netqasm_logger
from squidasm.sdk import NetSquidConnection, NetSquidSocket

logger = get_netqasm_logger()


def main(track_lines=True, log_subroutines_dir=None, phi=0., theta=0.):

    # Create a socket to recv classical information
    socket = NetSquidSocket("bob", "alice")

    # Initialize the connection
    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_from="alice",
    )
    with bob:
        epr = bob.recvEPR("alice")[0]
        bob.flush()

        # Get the corrections
        msg = socket.recv()
        logger.info(f"bob got corrections: {msg}")
        m1, m2 = eval(msg)
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()

        # To check states for debugging
        bob._release_qubits_on_exit = False


if __name__ == "__main__":
    main()
