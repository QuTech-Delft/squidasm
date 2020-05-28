from netqasm.sdk import Qubit
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from netqasm.logging import get_netqasm_logger

from shared.myfuncs import custom_send, custom_measure

logger = get_netqasm_logger()


def main(track_lines=True, log_subroutines_dir=None, app_dir=None):
    socket = Socket("alice", "bob", comm_log_dir=log_subroutines_dir, track_lines=True, app_dir=app_dir)

    # Initialize the connection to the backend
    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        app_dir=app_dir,
        log_subroutines_dir=log_subroutines_dir,
    )

    with alice:
        q1 = Qubit(alice)
        q1.measure()
        q2 = Qubit(alice)
        custom_measure(q2)
        

    socket.send("hello from main()")
    custom_send(socket)


if __name__ == "__main__":
    main()
