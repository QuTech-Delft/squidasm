import logging
from dataclasses import dataclass

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.toolbox.state_prep import set_qubit_state

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network, get_qubit_state, get_reference_state


@dataclass
class TeleportParams:
    phi: float = 0.0
    theta: float = 0.0

    @classmethod
    def generate_random_params(cls):
        """Create random parameters for a distributed CNOT program"""
        params = cls()
        params.theta = numpy.random.random() * numpy.pi
        params.phi = numpy.random.random() * numpy.pi
        return params


class SenderProgram(Program):
    PEER_NAME = "Receiver"

    def __init__(self, params: TeleportParams):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.phi = params.phi
        self.theta = params.theta

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="controller_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)

        # Create EPR pairs
        epr = epr_socket.create_keep()[0]

        # Teleport
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()
        yield from connection.flush()

        # Send the correction information
        m1, m2 = int(m1), int(m2)

        self.logger.info(
            f"Performed teleportation protocol with measured corrections: m1 = {m1}, m2 = {m2}"
        )

        csocket.send_structured(StructuredMessage("Corrections", f"{m1},{m2}"))

        original_dm = get_reference_state(self.phi, self.theta)

        return {"m1": m1, "m2": m2, "original_dm": original_dm}


class ReceiverProgram(Program):
    PEER_NAME = "Sender"

    def __init__(self):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="controller_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        epr = epr_socket.recv_keep()[0]
        yield from connection.flush()
        self.logger.info("Created EPR pair")

        # Get the corrections
        msg = yield from csocket.recv_structured()
        assert isinstance(msg, StructuredMessage)
        m1, m2 = msg.payload.split(",")
        self.logger.info(f"Received corrections: {m1}, {m2}")
        if int(m2) == 1:
            self.logger.info("performing X correction")
            epr.X()
        if int(m1) == 1:
            self.logger.info("performing Z correction")
            epr.Z()

        yield from connection.flush()

        final_dm = get_qubit_state(epr, "Receiver")

        return {"final_dm": final_dm}


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Receiver", "Sender"])

    # generate parameters randomly
    params = TeleportParams.generate_random_params()

    # Create instances of programs to run
    receiver_program = ReceiverProgram()
    sender_program = SenderProgram(params)

    # toggle logging. Set to logging.INFO for logging of events.
    receiver_program.logger.setLevel(logging.ERROR)
    sender_program.logger.setLevel(logging.ERROR)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    receiver_result, sender_result = run(
        config=cfg,
        programs={"Receiver": receiver_program, "Sender": sender_program},
        num_times=1,
    )

    print(params)

    print(f"State to teleport:\n{sender_result[0]['original_dm']}")
    print(f"State received:\n{receiver_result[0]['final_dm']}")
