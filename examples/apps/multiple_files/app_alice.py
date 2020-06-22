from netqasm.sdk import Qubit
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from netqasm.logging import get_netqasm_logger

from shared.myfuncs import custom_send, custom_measure

logger = get_netqasm_logger()


def main(log_config=None):
    socket = Socket("alice", "bob", log_config=log_config)

    # Initialize the connection to the backend
    alice = NetSquidConnection(
        name="alice",
        log_config=log_config
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
