from typing import List

from netqasm.sdk.connection import BaseNetQASMConnection
from netsquid_netbuilder.logger import LogManager
from netsquid_protocols import CSocketListener, QueueProtocol, SleepingProtocol

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

REQUEST_EPR_PAIR_GENERATION_MSG = "Request to initiate EPR pair generation"
CONFIRM_EPR_PAIR_GENERATION_MSG = "confirmation to initiate EPR pair generation"


class ClientProgram(Program):
    def __init__(self, node_name: str, server_name: str, request_start_time=0):
        self.node_name = node_name
        self.server_name = server_name
        self.logger = LogManager.get_stack_logger(f"Program {self.node_name}")
        self.request_start_time = request_start_time

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.server_name],
            epr_sockets=[self.server_name],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.server_name]
        epr_socket = context.epr_sockets[self.server_name]
        connection = context.connection

        # Wait to the desired time using a SleepingProtocol
        sleeping_protocol = SleepingProtocol()
        yield from sleeping_protocol.sleep(end_time=self.request_start_time)

        # submit the request to the server
        message = REQUEST_EPR_PAIR_GENERATION_MSG
        csocket.send(message)
        self.logger.info(f"sending message {message} to {self.server_name}")

        # wait for confirmation from the server
        message = yield from csocket.recv()
        self.logger.info(f"received message {message} from {self.server_name}")
        if message != CONFIRM_EPR_PAIR_GENERATION_MSG:
            raise RuntimeError(f"Expected confirmation but received: {message}")

        # Execute the request
        epr_qubit = epr_socket.create_keep()[0]
        epr_qubit.H()
        result = epr_qubit.measure()
        yield from connection.flush()
        self.logger.info(f"measures local EPR qubit: {result}")

        return {}


class ServerProgram(Program):
    def __init__(self, clients: List[str]):
        self.clients = clients
        self.node_name = "server"
        self.logger = LogManager.get_stack_logger(f"Program {self.node_name}")

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

        # We use the Queue protocol to manage the queue and signal for new queue items
        queue_protocol = QueueProtocol()
        queue_protocol.start()

        # Set up a CSocketListener for each client that will forward requests to the queue
        for client in self.clients:
            listener = CSocketListener(context, client, queue_protocol, self.logger)
            listener.start()

        while True:
            # Wait for a new request if applicable and process the next item in the queue
            client_name, msg = yield from queue_protocol.pop()
            csocket = context.csockets[client_name]
            epr_socket = context.epr_sockets[client_name]

            if msg != REQUEST_EPR_PAIR_GENERATION_MSG:
                raise RuntimeError(f"Received unsupported request: {msg}")
            self.logger.info(f"start processing request from {client_name}")

            # Send confirmation to the client
            message = CONFIRM_EPR_PAIR_GENERATION_MSG
            csocket.send(message)
            self.logger.info(f"sending message {message} to {client_name}")

            # Start processing the request
            epr_qubit = epr_socket.recv_keep()[0]
            epr_qubit.H()
            result = epr_qubit.measure()
            yield from connection.flush()
            self.logger.info(f"measures local EPR qubit: {result}")
