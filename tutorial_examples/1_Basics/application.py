from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    PEER_NAME = "Bob"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        # get classical socket to peer
        csocket = context.csockets[self.PEER_NAME]
        # get EPR socket to peer
        epr_socket = context.epr_sockets[self.PEER_NAME]
        # get connection to quantum network processing unit
        connection = context.connection

        # send a string message via a classical channel
        message = "Hello"
        csocket.send(message)
        print(f"Alice sends message: {message}")

        # Register a request to create an EPR pair, then apply a Hadamard gate on the epr qubit and measure
        epr_qubit = epr_socket.create_keep()[0]
        epr_qubit.H()
        result = epr_qubit.measure()
        yield from connection.flush()
        print(f"Alice measures local EPR qubit: {result}")

        # Qubits on a local node can be obtained, but require the connection to be initialized
        local_qubit0 = Qubit(connection)
        local_qubit1 = Qubit(connection)

        # Apply a Hadamard gate
        local_qubit0.H()
        # Apply CNOT gate where q0 is the control qubit, q1 is the target qubit
        local_qubit0.cnot(local_qubit1)

        r0 = local_qubit0.measure()
        r1 = local_qubit1.measure()

        yield from connection.flush()
        print(f"Alice measures local qubits: {r0}, {r1}")

        return {}


class BobProgram(Program):
    PEER_NAME = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        # get classical socket to peer
        csocket: Socket = context.csockets[self.PEER_NAME]
        # get EPR socket to peer
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        # get connection to quantum network processing unit
        connection: BaseNetQASMConnection = context.connection

        # Bob listens for messages on his classical socket
        message = yield from csocket.recv()
        print(f"Bob receives message: {message}")

        # Listen for request to create EPR pair, apply a Hadamard gate on the epr qubit and measure
        epr_qubit = epr_socket.recv_keep()[0]
        epr_qubit.H()
        result = epr_qubit.measure()
        yield from connection.flush()
        print(f"Bob measures local EPR qubit: {result}")

        return {}
