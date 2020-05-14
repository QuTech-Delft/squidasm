import random
from time import sleep

from netqasm.sdk.toolbox.measurements import parity_meas
from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def main():

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("Bob")

    # Initialize the connection
    with NetSquidConnection("Alice", epr_sockets=[epr_socket]) as Alice:

        # Wait a little for recv rules to be installed
        sleep(0.1)

        # Create EPR pairs
        q1 = epr_socket.create()[0]
        q2 = epr_socket.create()[0]

        # TODO put in single subroutine?
        Alice.flush()

        # Make sure we order the qubits consistently with Bob
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if q1_ID < q2_ID:
            qa = q1
            qc = q2
        else:
            qa = q2
            qc = q1

        # Get the row
        row = random.randint(0, 2)

        # Perform the three measurements
        if row == 0:
            m0 = parity_meas([qa, qc], "XI", Alice)
            m1 = parity_meas([qa, qc], "XX", Alice)
            m2 = parity_meas([qa, qc], "IX", Alice)
        elif row == 1:
            m0 = parity_meas([qa, qc], "XZ", Alice, negative=True)
            m1 = parity_meas([qa, qc], "YY", Alice)
            m2 = parity_meas([qa, qc], "ZX", Alice, negative=True)
        elif row == 2:
            m0 = parity_meas([qa, qc], "IZ", Alice)
            m1 = parity_meas([qa, qc], "ZZ", Alice)
            m2 = parity_meas([qa, qc], "ZI", Alice)
        else:
            raise ValueError(f"Not a row in the square {row}")

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += f"App Alice: row is:\n"
    for _ in range(row):
        to_print += "(___)\n"
    to_print += f"({m0}{m1}{m2})\n"
    for _ in range(2-row):
        to_print += "(___)\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)


if __name__ == "__main__":
    main()
