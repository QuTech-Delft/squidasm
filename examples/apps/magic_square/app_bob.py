from netqasm.logging import get_netqasm_logger
from netqasm.sdk.toolbox.measurements import parity_meas
from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def _get_default_strategy():
    return [
        ['XI', '-XZ', 'IZ'],  # col 0
        ['XX', 'YY', 'ZZ'],  # col 1
        ['IX', '-ZX', 'ZI'],  # col 2
    ]


def main(track_lines=True, log_subroutines_dir=None, col=0, strategy=None):

    # Get the strategy
    if strategy is None:
        strategy = _get_default_strategy()
    if col >= len(strategy):
        raise ValueError(f"Not a col in the square {col}")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("alice")

    # Initialize the connection
    with NetSquidConnection("bob", epr_sockets=[epr_socket]) as bob:

        # Create EPR pairs
        q1 = epr_socket.recv()[0]
        q2 = epr_socket.recv()[0]

        bob.flush()

        # Make sure we order the qubits consistently with Alice
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if q1_ID < q2_ID:
            qb = q1
            qd = q2
        else:
            qb = q2
            qd = q1

        # Perform the three measurements
        m0, m1, m2 = (parity_meas([qb, qd], strategy[col][i]) for i in range(3))

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += f"App bob: column is:\n"
    to_print += "(" + "_"*col + str(m0) + "_"*(2-col) + ")\n"
    to_print += "(" + "_"*col + str(m1) + "_"*(2-col) + ")\n"
    to_print += "(" + "_"*col + str(m2) + "_"*(2-col) + ")\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)

    return {
        'col': [int(m0), int(m1), int(m2)],
    }


if __name__ == "__main__":
    main()
