from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from squidasm.sim_util import get_qubit_state

logger = get_netqasm_logger()


def main(track_lines=True, log_subroutines_dir=None):

    # Create a socket to recv classical information
    socket = Socket("bob", "alice", comm_log_dir=log_subroutines_dir)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("alice")

    # Initialize the connection
    bob = NetSquidConnection(
        "bob",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=[epr_socket]
    )
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

        # Get the qubit state
        # NOTE only possible in simulation, not part of actual application
        dm = get_qubit_state(epr)
        return {"qubit_state": dm.tolist()}


if __name__ == "__main__":
    main()
