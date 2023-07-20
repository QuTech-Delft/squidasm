import logging
from dataclasses import dataclass

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.toolbox.state_prep import set_qubit_state
from util import (
    create_two_node_network,
    get_qubit_state,
    get_reference_state,
    teleport_recv,
    teleport_send,
)

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


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
        connection = context.connection

        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)

        yield from teleport_send(q, context, peer_name=self.PEER_NAME)

        original_dm = get_reference_state(self.phi, self.theta)

        return {"original_dm": original_dm}


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

        q = yield from teleport_recv(context, peer_name=self.PEER_NAME)

        final_dm = get_qubit_state(q, "Receiver")

        return {"final_dm": final_dm}


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Receiver", "Sender"])

    # generate parameters randomly
    params = TeleportParams.generate_random_params()

    # Create instances of programs to run
    receiver_program = ReceiverProgram()
    sender_program = SenderProgram(params)

    # toggle logging
    receiver_program.logger.setLevel(logging.INFO)
    sender_program.logger.setLevel(logging.INFO)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    receiver_result, sender_result = run(
        config=cfg,
        programs={"Receiver": receiver_program, "Sender": sender_program},
        num_times=1,
    )

    print(params)

    print(f"State to teleport:\n{sender_result[0]['original_dm']}")
    print(f"State received:\n{receiver_result[0]['final_dm']}")
