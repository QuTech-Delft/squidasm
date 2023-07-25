import logging
from dataclasses import dataclass

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.toolbox.state_prep import set_qubit_state

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network, get_qubit_state, get_reference_state
from squidasm.util.routines import (
    distributed_CNOT_control,
    distributed_CNOT_target,
    distributed_CPhase_control,
    distributed_CPhase_target,
)


@dataclass
class DistributedCGateParams:
    phi: float = 0.0
    theta: float = 0.0
    gate: str = "cnot"

    @classmethod
    def generate_random_params(cls):
        """Create random parameters for a distributed CNOT program"""
        params = cls()
        params.theta = numpy.random.random() * numpy.pi
        params.phi = numpy.random.random() * numpy.pi
        return params


class ControllerProgram(Program):
    PEER_NAME = "Target"

    def __init__(self, params: DistributedCGateParams):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.phi = params.phi
        self.theta = params.theta
        self.gate = params.gate

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

        # Prepare the control qubit
        ctrl_qubit = Qubit(connection)
        set_qubit_state(ctrl_qubit, self.phi, self.theta)

        # Use the control qubit for a distributed two qubit operation.
        if self.gate == "cnot":
            yield from distributed_CNOT_control(
                context, peer_name=self.PEER_NAME, ctrl_qubit=ctrl_qubit
            )
        elif self.gate == "cphase":
            yield from distributed_CPhase_control(
                context, peer_name=self.PEER_NAME, ctrl_qubit=ctrl_qubit
            )
        else:
            ValueError(
                f"{self.gate} does not match an implemented distributed controlled qubit gate"
            )

        # Retrieve qubit state to view results
        final_dm = get_qubit_state(ctrl_qubit, "Controller")
        original_dm = get_reference_state(self.phi, self.theta)

        return {
            "final_dm": final_dm,
            "original_dm": original_dm,
        }


class TargetProgram(Program):
    PEER_NAME = "Controller"

    def __init__(self, params: DistributedCGateParams):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.phi = params.phi
        self.theta = params.theta
        self.gate = params.gate

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

        # Prepare target qubit
        target_qubit = Qubit(connection)
        set_qubit_state(target_qubit, self.phi, self.theta)

        # Use target qubit for a distributed two qubit operation.
        if self.gate == "cnot":
            yield from distributed_CNOT_target(
                context, peer_name=self.PEER_NAME, target_qubit=target_qubit
            )
        elif self.gate == "cphase":
            yield from distributed_CPhase_target(
                context, peer_name=self.PEER_NAME, target_qubit=target_qubit
            )
        else:
            ValueError(
                f"{self.gate} does not match an implemented distributed controlled qubit gate"
            )

        # Retrieve qubit state to view results
        final_dm = get_qubit_state(target_qubit, "Target")
        original_dm = get_reference_state(self.phi, self.theta)

        return {
            "final_dm": final_dm,
            "original_dm": original_dm,
        }


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Target", "Controller"])

    # Choose CNOT parameters
    use_random_params = False
    if use_random_params:
        target_params = DistributedCGateParams.generate_random_params()
        controller_params = DistributedCGateParams.generate_random_params()
    else:
        # Set both target & control in 1 state -> control is unaffected & target should become 0
        target_params = DistributedCGateParams()
        target_params.theta = numpy.pi
        controller_params = DistributedCGateParams()
        controller_params.theta = numpy.pi

    # Choose gate to use. Two options available: cnot and cphase
    gate = "cnot"
    target_params.gate = gate
    controller_params.gate = gate

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
