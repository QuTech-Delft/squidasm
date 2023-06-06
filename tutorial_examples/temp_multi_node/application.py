from typing import List

from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    def __init__(self, server_name: str):
        self.server_name = server_name

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.server_name],
            epr_sockets=[self.server_name],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        # get classical socket to peer
        csocket = context.csockets[self.server_name]
        # get EPR socket to peer
        epr_socket = context.epr_sockets[self.server_name]
        # get connection to quantum network processing unit
        connection = context.connection

        # Bob listens for messages on his classical socket
        message = yield from csocket.recv()
        print(f"Client receives message: {message}")

        # Listen for request to create EPR pair, apply a Hadamard gate on the epr qubit and measure
        epr_qubit = epr_socket.recv_keep()[0]
        epr_qubit.H()
        result = epr_qubit.measure()
        yield from connection.flush()
        print(f"Client measures local EPR qubit: {result}")

        return {}


class ServerProgram(Program):
    def __init__(self, clients: List[str]):
        self.clients = clients

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=self.clients,
            epr_sockets=self.clients,
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        connection: BaseNetQASMConnection = context.connection

        for client in self.clients:
            # get classical socket to peer
            csocket: Socket = context.csockets[client]
            epr_socket: EPRSocket = context.epr_sockets[client]

            # send a string message via a classical channel
            message = f"Hello from server, client: {client} you may start"
            csocket.send(message)
            print(f"Server sends message: {message}")

            # Register a request to create an EPR pair, then apply a Hadamard gate on the epr qubit and measure
            epr_qubit = epr_socket.create_keep()[0]
            epr_qubit.H()
            result = epr_qubit.measure()
            yield from connection.flush()
            print(f"Server measures local EPR qubit: {result}")

        return {}
