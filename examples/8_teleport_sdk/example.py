import logging
import numpy as np
from time import sleep

from netqasm.sdk import Qubit, ThreadSocket
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications


def main():
    logging.basicConfig(level=logging.DEBUG)
    alice_id = 0
    bob_id = 1

    def run_alice():
        socket = ThreadSocket(alice_id, bob_id)
        with NetSquidConnection("Alice") as alice:
            # Wait a little to Bob has installed rule to recv
            sleep(0.1)

            # Create a qubit
            q = Qubit(alice)
            q.H()

            # Create entanglement
            epr = alice.createEPR("Bob")[0]

            # Teleport
            q.cnot(epr)
            q.H()
            m1 = q.measure()
            m2 = epr.measure()
            logging.info(f"m1, m2 = {m1}, {m2}")

        # Send the correction information
        msg = str((int(m1), int(m2)))
        socket.send(msg)

    def run_bob():
        socket = ThreadSocket(bob_id, alice_id)
        with NetSquidConnection("Bob") as bob:
            epr = bob.recvEPR("Alice")[0]
            bob.flush()

            # Get the corrections
            msg = socket.recv()
            logging.info(f"Bob got corrections: {msg}")
            m1, m2 = eval(msg)
            if m2 == 1:
                epr.X()
            if m1 == 1:
                epr.Z()

    def post_function(backend):
        shared_memory_alice = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        logging.info(shared_memory_alice[:5])
        m1, m2 = shared_memory_alice[0:2]
        state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
        logging.info(f"state = {state}")
        expected = np.array([[0.5, 0.5], [0.5, 0.5]])
        logging.info(f"expected = {expected}")
        assert np.all(np.isclose(expected, state))

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    }, post_function=post_function)


if __name__ == '__main__':
    main()
