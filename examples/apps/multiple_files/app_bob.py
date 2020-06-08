from netqasm.sdk import Qubit
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from netqasm.logging import get_netqasm_logger

from shared.myfuncs import custom_recv, custom_measure

logger = get_netqasm_logger()


def main(log_config=None):
    socket = Socket("bob", "alice", log_config=log_config)

    # Initialize the connection to the backend
    bob = NetSquidConnection(
        name="bob",
        log_config=log_config
    )
    with bob:
        q = Qubit(bob)
        custom_measure(q)

    socket.recv()
    custom_recv(socket)


if __name__ == "__main__":
    main()
