import unittest
from dataclasses import dataclass, field
from typing import List, Optional

import netsquid as ns
import numpy as np
from netqasm.sdk.qubit import Qubit
from netsquid_netbuilder.modules.qdevices import GenericQDeviceConfig
from netsquid_netbuilder.network_config import NetworkConfig, ProcessingNodeConfig
from netsquid_netbuilder.util.network_generation import (
    create_complete_graph_network_simplified,
)

from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


def _create_single_node_network(qdevice_cfg: GenericQDeviceConfig):
    node = ProcessingNodeConfig(
        name="Alice", qdevice_typ="generic", qdevice_cfg=qdevice_cfg
    )
    return NetworkConfig(processing_nodes=[node], links=[], clinks=[])


@dataclass
class GateOperation:
    gate_name: str
    """Gate operation to be done"""
    qubit_id: int = 0
    """Qubit ID to be operated"""
    control_qubit_id: Optional[int] = None
    """Optional argument for two qubit gate operations"""
    kwargs: dict = field(default_factory=dict)
    """Optional argument to set extra kwargs"""


class GateTestProgram(Program):
    def __init__(self, num_qubits: int, gates: List[GateOperation]):
        """
        Test program that creates a number of qubits, performs the desired gates and measures all qubits.
        :param num_qubits: Number of qubits to be created.
        :param gates: List of GateOperations to be executed.
        """
        self.num_qubits = num_qubits
        self.gates = gates

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="test_program",
            csockets=[],
            epr_sockets=[],
            max_qubits=self.num_qubits,
        )

    @staticmethod
    def _execute_gate(gate: GateOperation, qubits: List[Qubit]):
        target_qubit = qubits[gate.qubit_id]
        if gate.control_qubit_id is not None:
            control_qubit = qubits[gate.control_qubit_id]
            opp = control_qubit.__getattribute__(gate.gate_name)
            opp(target_qubit, **gate.kwargs)
        else:
            opp = target_qubit.__getattribute__(gate.gate_name)
            opp(**gate.kwargs)

    def run(self, context: ProgramContext):
        connection = context.connection

        qubits = [Qubit(connection) for _ in range(self.num_qubits)]

        for gate in self.gates:
            self._execute_gate(gate, qubits)

        measurements = [qubit.measure() for qubit in qubits]

        start_time = ns.sim_time()
        yield from connection.flush()
        completion_time = ns.sim_time() - start_time
        measurements = (int(x) for x in measurements)

        return {"measurements": measurements, "completion_time": completion_time}


class TestGates(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        ns.set_random_state(seed=42)
        ns.set_qstate_formalism(ns.QFormalism.KET)

    def tearDown(self) -> None:
        pass

    @staticmethod
    def _average_results(results: List[dict]) -> List[float]:
        measurements = np.array([list(item["measurements"]) for item in results])
        return np.average(measurements, axis=0)

    def _run_single_qubit_test(
        self,
        gates: List[GateOperation],
        expectation_average_meas: float,
        delta: float,
        qdevice_noise: float = 0.0,
    ):
        """Test that assumes only one qubit, it will execute the listed single gate operations,
        check the average results against the given expectation value and
         check that the duration of the operation is as expected.

        :param gates: List of GateOperations to be executed.
        :param expectation_average_meas: The expected mean of measured qubit
        :param delta: The tolerated deviation from this mean
        :param qdevice_noise: Noise level of operations on the qdevice"""
        qdevice_op_time = 100
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice"],
            qdevice_op_time=qdevice_op_time,
            qdevice_noise=qdevice_noise,
        )
        program = GateTestProgram(num_qubits=1, gates=gates)
        results = run(config=network_cfg, programs={"Alice": program}, num_times=10)[0]

        average_meas = self._average_results(results)[0]
        self.assertAlmostEqual(average_meas, expectation_average_meas, delta=delta)

        for result in results:
            self.assertAlmostEqual(
                result["completion_time"],
                qdevice_op_time * (2 + len(gates)),
                delta=1e-9,
            )

    def _run_two_qubit_test(
        self,
        gates: List[GateOperation],
        expectation_meas_qubit_0: float,
        expectation_meas_qubit_1: float,
        delta: float,
        expected_completion_time: float,
    ):
        """Test that assumes two qubits, it will execute the listed gate operations,
        check the average results against the given expectation value per qubit and
         that the operations took as long as expected.

        :param gates: List of GateOperations to be executed.
        :param expectation_meas_qubit_0: The expected mean of first qubit
        :param expectation_meas_qubit_1: The expected mean of second qubit
        :param delta: The tolerated deviation from the means
        :param expected_completion_time: Expectation for how long the operations should take"""
        qdevice_op_time = 100
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice"], qdevice_op_time=qdevice_op_time
        )
        program = GateTestProgram(num_qubits=2, gates=gates)
        results = run(config=network_cfg, programs={"Alice": program}, num_times=10)[0]

        average_meas = self._average_results(results)
        self.assertAlmostEqual(average_meas[0], expectation_meas_qubit_0, delta=delta)
        self.assertAlmostEqual(average_meas[1], expectation_meas_qubit_1, delta=delta)

        for result in results:
            self.assertAlmostEqual(
                result["completion_time"], expected_completion_time, delta=1e-9
            )

    def test_init(self):
        self._run_single_qubit_test(gates=[], expectation_average_meas=0, delta=0.01)

    def test_H(self):
        self._run_single_qubit_test(
            gates=[GateOperation("H")], expectation_average_meas=0.5, delta=0.21
        )

    def test_double_H(self):
        self._run_single_qubit_test(
            gates=[GateOperation("H"), GateOperation("H")],
            expectation_average_meas=0,
            delta=0.01,
        )

    def test_X(self):
        self._run_single_qubit_test(
            gates=[GateOperation("X")], expectation_average_meas=1, delta=0.01
        )

    def test_Y(self):
        self._run_single_qubit_test(
            gates=[GateOperation("Y")], expectation_average_meas=1, delta=0.01
        )

    def test_Z(self):
        self._run_single_qubit_test(
            gates=[GateOperation("Z")], expectation_average_meas=0, delta=0.01
        )

    def test_repeated_gate_with_noise(self):
        """Check that doing a lot of operations with noise leads to qubits being random in the end"""
        self._run_single_qubit_test(
            gates=[
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
                GateOperation("Z"),
            ],
            expectation_average_meas=0.5,
            delta=0.21,
            qdevice_noise=0.2,
        )

    def test_cnot_1(self):
        self._run_two_qubit_test(
            gates=[GateOperation("cnot", qubit_id=1, control_qubit_id=0)],
            expectation_meas_qubit_0=0,
            expectation_meas_qubit_1=0,
            delta=0.01,
            expected_completion_time=500,
        )

    def test_cnot_2(self):
        self._run_two_qubit_test(
            gates=[
                GateOperation("X"),
                GateOperation("cnot", qubit_id=1, control_qubit_id=0),
            ],
            expectation_meas_qubit_0=1,
            expectation_meas_qubit_1=1,
            delta=0.01,
            expected_completion_time=600,
        )

    def test_cphase(self):
        self._run_two_qubit_test(
            gates=[GateOperation("cphase", qubit_id=1, control_qubit_id=0)],
            expectation_meas_qubit_0=0,
            expectation_meas_qubit_1=0,
            delta=0.01,
            expected_completion_time=500,
        )

    def test_decoherence_none(self):
        """Check that qubits do not experience decoherence if it is disabled"""
        qdevice_op_time = 1e8
        decoherence_time_scale = 0

        qdevice_cfg = GenericQDeviceConfig.perfect_config(num_qubits=2)
        qdevice_cfg.T1 = decoherence_time_scale
        qdevice_cfg.T2 = decoherence_time_scale
        qdevice_cfg.single_qubit_gate_time = qdevice_op_time
        network_cfg = _create_single_node_network(qdevice_cfg)

        program = GateTestProgram(num_qubits=2, gates=[GateOperation("X")])
        results = run(config=network_cfg, programs={"Alice": program}, num_times=40)[0]

        average_meas = self._average_results(results)
        # In process qubit does not experience decoherence
        self.assertAlmostEqual(average_meas[0], 1, delta=0.01)
        self.assertAlmostEqual(average_meas[1], 0.0, delta=0.1)

    def test_decoherence_small(self):
        """Check that qubits not undergoing operations experience decoherence"""
        qdevice_op_time = 10
        decoherence_time_scale = 40

        qdevice_cfg = GenericQDeviceConfig.perfect_config(num_qubits=2)
        qdevice_cfg.T1 = decoherence_time_scale
        qdevice_cfg.T2 = decoherence_time_scale
        qdevice_cfg.single_qubit_gate_time = qdevice_op_time
        network_cfg = _create_single_node_network(qdevice_cfg)

        program = GateTestProgram(num_qubits=2, gates=[GateOperation("X")])
        results = run(config=network_cfg, programs={"Alice": program}, num_times=40)[0]

        average_meas = self._average_results(results)
        # In process qubit does not experience decoherence
        self.assertAlmostEqual(average_meas[0], 1, delta=0.01)
        # Expect some error due to decoherence, but still small
        self.assertGreater(average_meas[1], 0)
        self.assertAlmostEqual(average_meas[1], 0.0, delta=0.1)

    def test_decoherence_large(self):
        """Check that qubits not undergoing operation experience decoherence and
        that under large decoherence its results are random in the end.
        Starting state is 0 for decoherence test qubit"""
        qdevice_op_time = 10
        decoherence_time_scale = 1

        qdevice_cfg = GenericQDeviceConfig.perfect_config(num_qubits=2)
        qdevice_cfg.T1 = decoherence_time_scale
        qdevice_cfg.T2 = decoherence_time_scale
        qdevice_cfg.single_qubit_gate_time = qdevice_op_time
        network_cfg = _create_single_node_network(qdevice_cfg)

        program = GateTestProgram(num_qubits=2, gates=[GateOperation("X")])
        results = run(config=network_cfg, programs={"Alice": program}, num_times=40)[0]

        average_meas = self._average_results(results)
        # In process qubit does not experience decoherence
        self.assertAlmostEqual(average_meas[0], 1, delta=0.01)
        # Expect qubit result to be random
        self.assertAlmostEqual(average_meas[1], 0.5, delta=0.1)

    def test_decoherence_large_2(self):
        """Check that qubits not undergoing operation experience decoherence and
        that under large decoherence its results are random in the end.
        Starting state is 1 for decoherence test qubit."""
        qdevice_op_time = 10
        decoherence_time_scale = 1

        qdevice_cfg = GenericQDeviceConfig.perfect_config(num_qubits=2)
        qdevice_cfg.T1 = decoherence_time_scale
        qdevice_cfg.T2 = decoherence_time_scale
        qdevice_cfg.single_qubit_gate_time = qdevice_op_time
        network_cfg = _create_single_node_network(qdevice_cfg)

        program = GateTestProgram(
            num_qubits=2, gates=[GateOperation("X", qubit_id=1), GateOperation("X")]
        )
        results = run(config=network_cfg, programs={"Alice": program}, num_times=40)[0]

        average_meas = self._average_results(results)
        # Expect qubit result to be random
        self.assertAlmostEqual(average_meas[1], 0.5, delta=0.1)

    @unittest.expectedFailure  # Stationary state of decoherence in a T1T2NoiseModel
    # in DM formalism is set to |0> which produces different behaviour with respect to Ket formalism
    def test_decoherence_large_dm_formalism(self):
        """Check that qubits not undergoing operation experience decoherence and
        that under large decoherence its results are random in the end.
        Starting state is 0 for decoherence test qubit.
        This test checks that the outcome is identical when using DM formalism"""
        ns.set_qstate_formalism(ns.QFormalism.DM)

        qdevice_op_time = 10
        decoherence_time_scale = 1

        qdevice_cfg = GenericQDeviceConfig.perfect_config(num_qubits=2)
        qdevice_cfg.T1 = decoherence_time_scale
        qdevice_cfg.T2 = decoherence_time_scale
        qdevice_cfg.single_qubit_gate_time = qdevice_op_time
        network_cfg = _create_single_node_network(qdevice_cfg)

        program = GateTestProgram(num_qubits=2, gates=[GateOperation("X")])
        results = run(config=network_cfg, programs={"Alice": program}, num_times=40)[0]

        average_meas = self._average_results(results)
        # In process qubit does not experience decoherence
        self.assertAlmostEqual(average_meas[0], 1, delta=0.01)
        # Expect qubit result to be random
        self.assertAlmostEqual(average_meas[1], 0.5, delta=0.1)


if __name__ == "__main__":
    unittest.main()
