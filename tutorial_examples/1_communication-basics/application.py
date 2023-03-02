from netqasm.sdk.classical_communication.message import StructuredMessage
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
        # get connection to quantum device controller
        connection = context.connection

        # Classical communication Alice

        # send a string message via a classical channel
        message = "start protocol at time: xx:xx"
        csocket.send(message)
        print(f"Alice sends message: {message}")

        # receive the structured message
        callback_message = yield from csocket.recv_structured()
        assert isinstance(callback_message, StructuredMessage)
        print(f"Alice receives a structured message with header: {callback_message.header}"
              f" and payload: {callback_message.payload}")

        # Check the handshake received from Bob
        if callback_message.header != "echo" or callback_message.payload != message:
            raise Exception("Classical communication handshake failed")

        # Register a request to create an EPR pair, then apply a Hadamard gate on qubit and measure
        qubit = epr_socket.create_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        print(f"Alice measures local EPR qubit: {result}")

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
        # get connection to quantum device controller
        connection: BaseNetQASMConnection = context.connection

        # Bob listens for messages on his classical socket
        message = yield from csocket.recv()
        print(f"Bob receives message: {message}")

        # Bob sends confirmation by echoing the message from Alice, but with a StructuredMessage
        assert isinstance(message, str)
        callback_message = StructuredMessage(header="echo", payload=message)
        csocket.send_structured(callback_message)
        print(f"Bob sends structured message with header: {callback_message.header}"
              f" and payload: {callback_message.payload}")

        # Listen for request to create EPR pair, apply a Hadamard gate on qubit and measure
        qubit = epr_socket.recv_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        print(f"Bob measures local EPR qubit: {result}")

        return {}
