from netqasm.sdk.qubit import Qubit
from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    PEER_NAME = "Bob"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            parameters={},
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

        # Register a request to create an EPR pair, then apply a Hadamard gate on qubit and measure
        qubit = epr_socket.create_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        print(f"Alice measures local EPR qubit: {result}")

        # Qubits on a local node can be obtained, but require the connection to be initialized
        q0 = Qubit(connection)
        q1 = Qubit(connection)

        # Apply a Hadamard gate
        q0.H()
        # Apply CNOT gate where q0 is the control qubit, q1 is the target qubit
        q0.cnot(q1)

        r0 = q0.measure()
        r1 = q1.measure()

        yield from connection.flush()
        print(f"Alice measures local qubits: {r0}, {r1}")

        return {}


class BobProgram(Program):
    PEER_NAME = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            parameters={},
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

        # Listen for request to create EPR pair, apply a Hadamard gate on qubit and measure
        qubit = epr_socket.recv_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        print(f"Bob measures local EPR qubit: {result}")

        return {}
