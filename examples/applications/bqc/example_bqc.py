import logging
import math
from dataclasses import dataclass

import numpy
from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network, get_qubit_state
from squidasm.util.routines import (
    measXY,
    recv_float,
    recv_int,
    recv_remote_state_preparation,
    remote_state_preparation,
    send_float,
    send_int,
)


@dataclass
class BQCProgramParams:
    """BQC program parameters. alpha and beta are used for the effective computation,
    theta and r are used to obfuscate the computation from the server.
    dummy is used to test the server"""

    alpha: float = 0.0
    beta: float = 0.0
    theta1: float = 0.0
    theta2: float = 0.0
    r1: int = 0
    r2: int = 0
    dummy: int = 0

    @classmethod
    def generate_random_params(cls):
        """Create random parameters for a BQC program"""
        params = cls()
        params.alpha = numpy.random.random() * numpy.pi
        params.beta = numpy.random.random() * numpy.pi
        params.theta1 = numpy.random.random() * numpy.pi
        params.theta2 = numpy.random.random() * numpy.pi
        params.r1 = numpy.random.randint(0, 2)
        params.r2 = numpy.random.randint(0, 2)
        return params


class ClientProgram(Program):
    PEER_NAME = "Server"

    def __init__(self, params: BQCProgramParams):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.alpha = params.alpha
        self.beta = params.beta
        self.theta1 = params.theta1
        self.theta2 = params.theta2
        self.r1 = params.r1
        self.r2 = params.r2

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        # Send two qubits to the server.
        p1 = remote_state_preparation(epr_socket, self.theta1)
        p2 = remote_state_preparation(epr_socket, self.theta2)
        yield from connection.flush()
        self.logger.info("Remote state preparation finished.")
        # Convert outcomes to integers to use them in calculations below.
        p1, p2 = int(p1), int(p2)

        # Send first angle to server.
        delta1 = self.alpha - self.theta1 + (p1 + self.r1) * math.pi
        self.logger.info(f"Sending delta1 = {delta1}")
        send_float(csocket, delta1)

        # receive results of server measurement
        m1 = yield from recv_float(csocket)
        self.logger.info(f"Received m1 = {m1}")

        # Send second angle to server.
        delta2 = (
            math.pow(-1, (m1 + self.r1)) * self.beta
            - self.theta2
            + (p2 + self.r2) * math.pi
        )
        self.logger.info(f"Sending delta2 = {delta2}")
        send_float(csocket, delta2)

        # receive results of server measurement
        m2 = yield from recv_int(csocket)
        self.logger.info(f"Received m2 = {m2}")

        return {
            "delta1": delta1 / math.pi,
            "delta2": delta2 / math.pi,
            "p1": p1,
            "p2": p2,
            "m1": m1,
            "m2": m2,
        }


class ServerProgram(Program):
    PEER_NAME = "Client"

    def __init__(self):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket: Socket = context.csockets[self.PEER_NAME]
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        connection: BaseNetQASMConnection = context.connection

        # receive qubits from client
        q1 = recv_remote_state_preparation(epr_socket)
        q2 = recv_remote_state_preparation(epr_socket)

        # Apply a CPHASE gate between the two qubits.
        q1.cphase(q2)

        yield from connection.flush()
        self.logger.info("Remote state preparation and CPhase finished.")

        # Receive from the client the angle to measure the first qubit in.
        angle = yield from recv_float(csocket)
        self.logger.info(f"Received delta1 = {angle}")

        s = measXY(q1, angle)
        yield from connection.flush()
        send_int(csocket, int(s))
        self.logger.info(f"Sending m1 = {s}")

        # Receive from the client the angle to measure the first qubit in.
        angle = yield from recv_float(csocket)
        self.logger.info(f"Received delta2 = {angle}")

        q2.rot_Z(angle=angle)
        q2.H()

        yield from connection.flush()

        # Store final qubit state before measuring
        final_dm = get_qubit_state(q2, "Server")

        # measure result
        s = q2.measure()
        yield from connection.flush()
        send_int(csocket, int(s))
        self.logger.info(f"Sending m2 = {s}")

        return {"final_dm": final_dm}


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Client", "Server"])

    # generate BQC parameters randomly
    use_random_params = False
    if use_random_params:
        bqc_params = BQCProgramParams.generate_random_params()
    else:
        # Theta & r params are random, but alpha & beta chosen so final state is guaranteed 0 (m2=0 with 100% chance)
        # This parameter combination allows the client to check that the server is honest
        bqc_params = BQCProgramParams.generate_random_params()
        # r2 == 1 will flip the end result bit. Client can correct the result for this, but for simplicity we will use 0
        bqc_params.r2 = 0
        bqc_params.alpha = numpy.pi / 2
        bqc_params.beta = numpy.pi / 2

    # Create instances of programs to run
    client_program = ClientProgram(bqc_params)
    server_program = ServerProgram()

    # toggle logging. Set to logging.INFO for logging of events.
    client_program.logger.setLevel(logging.ERROR)
    server_program.logger.setLevel(logging.ERROR)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    client_results, server_results = run(
        config=cfg,
        programs={"Server": server_program, "Client": client_program},
        num_times=1,
    )

    print(f"Parameters used:\n{bqc_params.__dict__}")
    print(f"\nResults client:\n{client_results[0]}")

    print(
        f"\nFinal state created on server before measurement:\n{server_results[0]['final_dm']}"
    )
