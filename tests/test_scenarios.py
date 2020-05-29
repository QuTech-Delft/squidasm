from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from netqasm.logging import set_log_level, get_netqasm_logger
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator

logger = get_netqasm_logger()


def test_bi_directional_teleport():

    def teleport(q, conn, epr_socket, socket):
        # Create entanglement
        epr = epr_socket.create()[0]

        print(f'conn {conn.name} 1')

        # Teleport operations
        q.cnot(epr)
        q.H()
        m1 = q.measure(inplace=True)
        m2 = epr.measure(inplace=True)

        # Callback function for flush
        def teleport_callback():
            print(f'conn {conn.name} 3')
            # Send corrections
            msg = str((int(m1), int(m2)))
            socket.send(msg)
            print(f'conn {conn.name} 4')

        # Flush to get outcomes
        conn.flush(block=False, callback=teleport_callback)
        print(f'conn {conn.name} 2')

    def receive(conn, epr_socket, socket):
        # Create entanglement
        epr = epr_socket.recv()[0]

        # Callback function for flush
        def receive_callback():
            # Get the corrections
            msg = socket.recv()
            m1, m2 = eval(msg)
            if m2 == 1:
                epr.X()
            if m1 == 1:
                epr.Z()

        # Flush to execute
        print(f'conn {conn.name} recv block')
        conn.flush(block=True, callback=receive_callback)
        print(f'conn {conn.name} recv block FIN')

        return epr

    def run_alice():
        # Socket for classical messages
        socket = Socket("alice", "bob")

        # EPR socket for entanglement generation
        epr_socket = EPRSocket("bob")
        with NetSquidConnection("alice", epr_sockets=[epr_socket]) as alice:
            q1 = Qubit(alice)

            # Teleport
            print('alice 1')
            teleport(q1, alice, epr_socket, socket)
            print('alice 2')

            # Receive
            q2 = receive(alice, epr_socket, socket)
            print('alice 3')

            m = q2.measure()

            logger.info(f'alice: {m}')

    def run_bob():
        # Socket for classical messages
        socket = Socket("bob", "alice")

        # EPR socket for entanglement generation
        epr_socket = EPRSocket("alice")
        with NetSquidConnection("bob", epr_sockets=[epr_socket]) as bob:
            q1 = Qubit(bob)

            # Teleport
            print('bob 1')
            teleport(q1, bob, epr_socket, socket)
            print('bob 2')

            # Receive
            q2 = receive(bob, epr_socket, socket)
            print('bob 3')

            m = q2.measure()

            logger.info(f'bob: {m}')

    run_applications({
        "alice": run_alice,
        "bob": run_bob,
    })


def test_parallel_execution():

    def run_alice():
        # Two subroutines which would give a deadlock unless the execution can
        # switch between subroutines during execution.
        subroutine_1 = """
# NETQASM 0.0
# APPID 0
array(1) @0
array(1) @1
set R0 0
store R0 @0[0]
wait_all @1[0:1]
"""
        subroutine_2 = """
# NETQASM 0.0
# APPID 0
set R0 0
store R0 @1[0]
wait_all @0[0:1]
"""
        communicator = SimpleCommunicator("alice", subroutines=[
            subroutine_1,
            subroutine_2,
        ])
        communicator.run()

    run_applications({
        "alice": run_alice,
    })


import faulthandler, signal
faulthandler.register(signal.SIGUSR1)

if __name__ == "__main__":
    set_log_level('DEBUG')
    # set_log_level('INFO')
    # set_log_level('WARNING')
    test_bi_directional_teleport()
    # test_parallel_execution()
