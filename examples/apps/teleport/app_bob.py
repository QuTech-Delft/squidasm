from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from squidasm.sim_util import get_qubit_state

logger = get_netqasm_logger()


def main(app_config=None):

    # Create a socket to recv classical information
    socket = Socket("bob", "alice", log_config=app_config.log_config)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("alice")

    # Initialize the connection
    bob = NetSquidConnection(
        app_name=app_config.app_name,
        node_name=app_config.node_name,
        log_config=app_config.log_config,
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
