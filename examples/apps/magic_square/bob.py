import random

from netqasm.logging import get_netqasm_logger
from netqasm.sdk.toolbox.measurements import parity_meas
from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def main():

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("Alice")

    # Initialize the connection
    with NetSquidConnection("Bob", epr_sockets=[epr_socket]) as Bob:

        # Create EPR pairs
        q1 = epr_socket.recv()[0]
        q2 = epr_socket.recv()[0]

        Bob.flush()

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

        # Get the column
        col = random.randint(0, 2)

        # Perform the three measurements
        if col == 0:
            m0 = parity_meas([qb, qd], "XI", Bob)
            m1 = parity_meas([qb, qd], "XZ", Bob, negative=True)
            m2 = parity_meas([qb, qd], "IZ", Bob)
        elif col == 1:
            m0 = parity_meas([qb, qd], "XX", Bob)
            m1 = parity_meas([qb, qd], "YY", Bob)
            m2 = parity_meas([qb, qd], "ZZ", Bob)
        elif col == 2:
            m0 = parity_meas([qb, qd], "IX", Bob)
            m1 = parity_meas([qb, qd], "ZX", Bob, negative=True)
            m2 = parity_meas([qb, qd], "ZI", Bob)
        else:
            raise ValueError(f"Not a column in the square {col}")

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += f"App Bob: column is:\n"
    to_print += "(" + "_"*col + str(m0) + "_"*(2-col) + ")\n"
    to_print += "(" + "_"*col + str(m1) + "_"*(2-col) + ")\n"
    to_print += "(" + "_"*col + str(m2) + "_"*(2-col) + ")\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)


if __name__ == "__main__":
    main()
