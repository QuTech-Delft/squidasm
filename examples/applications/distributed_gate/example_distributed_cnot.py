import logging
from dataclasses import dataclass

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.toolbox.state_prep import set_qubit_state

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network, get_qubit_state, get_reference_state


@dataclass
class DistributedCNOTParams:
    phi: float = 0.0
    theta: float = 0.0

    @classmethod
    def generate_random_params(cls):
        """Create random parameters for a distributed CNOT program"""
        params = cls()
        params.theta = numpy.random.random() * numpy.pi
        params.phi = numpy.random.random() * numpy.pi
        return params


class ControllerProgram(Program):
    PEER_NAME = "Target"

    def __init__(self, params: DistributedCNOTParams):
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

        self.logger.info("Creating EPR pair with target...")
        # create one EPR pair with target
        epr = epr_socket.create_keep()[0]

        # initialize control qubit of the distributed CNOT
        yield from connection.flush()
        self.logger.info("Initializing control qubit...")
        ctrl_qubit = Qubit(connection)
        set_qubit_state(ctrl_qubit, self.phi, self.theta)
        yield from connection.flush()
        self.logger.info("Initialized control qubit")

        # Synchronize with other nodes for cleaner logs/animations in QNE.
        yield from csocket.recv()

        self.logger.info("Starting distributed CNOT...")
        # perform a local CNOT with `epr` and measure `epr`
        ctrl_qubit.cnot(epr)
        epr_meas = epr.measure()

        # let back-end execute the quantum operations above
        yield from connection.flush()

        # send the outcome to target
        csocket.send(str(epr_meas))

        # wait for target's measurement outcome to undo potential entanglement
        # between his EPR half and the original control qubit
        target_meas = yield from csocket.recv()
        if target_meas == "1":
            self.logger.info("Outcome = 1, so doing Z correction")
            ctrl_qubit.Z()
        else:
            self.logger.info("Outcome = 0, no corrections needed")

        yield from connection.flush()

        # ack the outcome
        csocket.send("ACK")

        final_dm = get_qubit_state(ctrl_qubit, "Controller")
        original_dm = get_reference_state(self.phi, self.theta)

        return {
            "epr_meas": int(epr_meas),
            "final_dm": final_dm,
            "original_dm": original_dm,
        }


class TargetProgram(Program):
    PEER_NAME = "Controller"

    def __init__(self, params: DistributedCNOTParams):
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

        self.logger.info("Creating EPR pair with controller...")
        # create one EPR pair with Controller
        epr = epr_socket.recv_keep()[0]

        # initialize target qubit of the distributed CNOT
        yield from connection.flush()
        self.logger.info("Initializing target qubit...")
        target_qubit = Qubit(connection)
        set_qubit_state(target_qubit, self.phi, self.theta)

        # let back-end execute the quantum operations above
        yield from connection.flush()
        self.logger.info("Initialized target qubit")

        csocket.send("")

        # wait for Controller's measurement outcome
        m = yield from csocket.recv()

        # if outcome = 1, apply an X gate on the local EPR half
        if m == "1":
            self.logger.info("Outcome = 1, so doing X correction")
            epr.X()
        else:
            self.logger.info("Outcome = 0, no correction needed")

        # At this point, `epr` is correlated with the control qubit on Controller's side.
        # (If Controller's control was in a superposition, `epr` is now entangled with it.)
        # Use `epr` as the control of a local CNOT on the target qubit.
        epr.cnot(target_qubit)

        yield from connection.flush()

        # undo any potential entanglement between `epr` and Controller's control qubit
        self.logger.info("Undo entanglement between control and EPR qubit")
        epr.H()
        epr_meas = epr.measure()
        yield from connection.flush()

        # Controller will do a controlled-Z based on the outcome to undo the entanglement
        csocket.send(str(epr_meas))

        # Wait for an ack before exiting
        msg = yield from csocket.recv()
        assert msg == "ACK"

        final_dm = get_qubit_state(target_qubit, "Target")
        original_dm = get_reference_state(self.phi, self.theta)

        return {
            "epr_meas": int(epr_meas),
            "final_dm": final_dm,
            "original_dm": original_dm,
        }


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Target", "Controller"])

    # Choose CNOT parameters
    use_random_params = False
    if use_random_params:
        target_params = DistributedCNOTParams.generate_random_params()
        controller_params = DistributedCNOTParams.generate_random_params()
    else:
        # Set both target & control in 1 state -> control is unaffected & target should become 0
        target_params = DistributedCNOTParams()
        target_params.theta = numpy.pi
        controller_params = DistributedCNOTParams()
        controller_params.theta = numpy.pi

    # Create instances of programs to run
    target_program = TargetProgram(target_params)
    controller_program = ControllerProgram(controller_params)

    # toggle logging. Set to logging.INFO for logging of events.
    target_program.logger.setLevel(logging.ERROR)
    controller_program.logger.setLevel(logging.ERROR)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    target_result, controller_result = run(
        config=cfg,
        programs={"Controller": controller_program, "Target": target_program},
        num_times=1,
    )

    print(target_params)
    print(controller_params)

    print(f"Original state target:\n{target_result[0]['original_dm']}")
    print(f"Original state controller:\n{controller_result[0]['original_dm']}")

    print(f"Final state target:\n{target_result[0]['final_dm']}")
    print(f"Final state controller:\n{controller_result[0]['final_dm']}")
