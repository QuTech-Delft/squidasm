from netqasm.sdk import Qubit
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from netqasm.logging import get_netqasm_logger

from shared.myfuncs import custom_recv, custom_measure

logger = get_netqasm_logger()


def main(track_lines=True, log_subroutines_dir=None, app_dir=None):
    logger.info(f"app_dir: {app_dir}")

    # Create a socket to send classical information
    socket = Socket("bob", "alice", comm_log_dir=log_subroutines_dir, track_lines=True, app_dir=app_dir)

    # Initialize the connection to the backend
    bob = NetSquidConnection(
        name="bob",
        track_lines=track_lines,
        app_dir=app_dir,
        log_subroutines_dir=log_subroutines_dir,
    )
    with bob:
        q = Qubit(bob)
        custom_measure(q)

    socket.recv()
    custom_recv(socket)


if __name__ == "__main__":
    main()
