from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def main(track_lines=True, log_subroutines_dir=None):

    # Create a socket to recv classical information
    socket = Socket("bob", "alice")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("alice")

    # Initialize the connection
    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=[epr_socket]
    )
    bob._clear_app_on_exit = False
    with bob:
        epr = epr_socket.recv()[0]
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
