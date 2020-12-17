# from netqasm.sdk import Qubit, EPRSocket
# from netqasm.sdk import ThreadSocket as Socket
# from netqasm.logging.glob import set_log_level, get_netqasm_logger
# from netqasm.runtime.app_config import default_app_config

# from squidasm.sdk import NetSquidConnection
# from squidasm.run import run_applications
# from squidasm.communicator import SimpleCommunicator

# logger = get_netqasm_logger()


# def test_bi_directional_teleport():

#     def teleport(q, conn, epr_socket, socket):
#         # Create entanglement
#         epr = epr_socket.create()[0]

#         # Teleport operations
#         q.cnot(epr)
#         q.H()
#         m1 = q.measure()
#         m2 = epr.measure()

#         # Callback function for flush
#         def teleport_callback():
#             # Send corrections
#             msg = str((int(m1), int(m2)))
#             socket.send(msg)

#         # Flush to get outcomes
#         conn.flush(block=False, callback=teleport_callback)

#     def receive(conn, epr_socket, socket):
#         # Create entanglement
#         epr = epr_socket.recv()[0]

#         # Callback function for flush
#         def receive_callback():
#             # Get the corrections
#             msg = socket.recv()
#             m1, m2 = eval(msg)
#             if m2 == 1:
#                 epr.X()
#             if m1 == 1:
#                 epr.Z()

#             conn.flush(block=True)

#         # Flush to execute
#         conn.flush(block=True, callback=receive_callback)

#         return epr

#     def run_alice():
#         # Socket for classical messages
#         socket = Socket("alice", "bob")

#         # EPR socket for entanglement generation
#         epr_socket = EPRSocket("bob")
#         with NetSquidConnection("alice", epr_sockets=[epr_socket]) as alice:
#             # NOTE We need to set this virtual address to 1 at this point since the created EPR pairs will
#             # get 0 (first unused since measure(inplace=False)) and we shouldn't compete with the
#             # position used by the EPR pairs
#             q1 = Qubit(alice, virtual_address=1)

#             # Teleport
#             teleport(q1, alice, epr_socket, socket)

#             # Receive
#             q2 = receive(alice, epr_socket, socket)

#             m = q2.measure()

#             alice.flush()

#             alice.block()

#             logger.info(f'alice: {m}')

#     def run_bob():
#         # Socket for classical messages
#         socket = Socket("bob", "alice")

#         # EPR socket for entanglement generation
#         epr_socket = EPRSocket("alice")
#         with NetSquidConnection("bob", epr_sockets=[epr_socket]) as bob:
#             q1 = Qubit(bob, virtual_address=1)

#             # Teleport
#             teleport(q1, bob, epr_socket, socket)

#             # Receive
#             q2 = receive(bob, epr_socket, socket)

#             m = q2.measure()

#             bob.flush()

#             bob.block()

#             logger.info(f'bob: {m}')

#     run_applications([
#         default_app_config("alice", run_alice),
#         default_app_config("bob", run_bob),
#     ], use_app_config=False)


# def test_parallel_execution():

#     def run_alice():
#         # Two subroutines which would give a deadlock unless the execution can
#         # switch between subroutines during execution.
#         subroutine_1 = """
# # NETQASM 0.0
# # APPID 0
# array(1) @0
# array(1) @1
# set R0 0
# store R0 @0[0]
# wait_all @1[0:1]
# """
#         subroutine_2 = """
# # NETQASM 0.0
# # APPID 0
# set R0 0
# store R0 @1[0]
# wait_all @0[0:1]
# """
#         communicator = SimpleCommunicator("alice", subroutines=[
#             subroutine_1,
#             subroutine_2,
#         ])
#         communicator.run()

#     run_applications([
#         default_app_config("alice", run_alice),
#     ], use_app_config=False)


# if __name__ == "__main__":
#     # set_log_level('INFO')
#     set_log_level('WARNING')
#     test_bi_directional_teleport()
#     # test_parallel_execution()
