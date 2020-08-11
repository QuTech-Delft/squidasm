from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection


def main(log_config=None):
    epr_socket_alice = EPRSocket("alice")

    socket_bob = Socket("repeater", "bob", log_config=log_config)
    epr_socket_bob = EPRSocket("bob")

    repeater = NetSquidConnection(
        name="repeater",
        log_config=log_config,
        epr_sockets=[epr_socket_alice, epr_socket_bob]
    )

    with repeater:
        # Wait for entanglement with Alice
        epr_alice = epr_socket_alice.recv()[0]

        # Create entanglement with Bob
        epr_bob = epr_socket_bob.create()[0]

        # Teleport qubit that is entangled with Alice to Bob
        epr_alice.cnot(epr_bob)
        epr_alice.H()
        m1 = epr_alice.measure()
        m2 = epr_bob.measure()

    m1, m2 = int(m1), int(m2)

    # Send teleportation corrections to Bob
    msg = str((m1, m2))
    socket_bob.send(msg)

    return {'m1': m1, 'm2': m2}


if __name__ == "__main__":
    main()
