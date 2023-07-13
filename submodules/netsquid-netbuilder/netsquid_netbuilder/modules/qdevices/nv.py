from __future__ import annotations

import numpy as np
from netsquid.components.instructions import (
    INSTR_CXDIR,
    INSTR_CYDIR,
    INSTR_INIT,
    INSTR_MEASURE,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
)
from netsquid.components.models.qerrormodels import DepolarNoiseModel, T1T2NoiseModel
from netsquid.components.qprocessor import PhysicalInstruction, QuantumProcessor
from netsquid.qubits.operators import Operator
from netsquid_netbuilder.modules.qdevices.interface import (
    IQDeviceBuilder,
    IQDeviceConfig,
)


class NVQDeviceConfig(IQDeviceConfig):
    """
    The configuration for a NV quantum device.
    """

    # number of qubits per NV
    num_qubits: int = 2
    """Number of qubits in the quantum device."""

    # single electron noise
    electron_init_depolar_prob: float = 0.05
    """Probability of error during electron initialization."""
    electron_single_qubit_depolar_prob: float = 0.0
    """Probability of error during electron single gate operation."""

    # measurement errors electron
    prob_error_0: float = 0.05
    """Probability of measuring a 1 instead of 0 in an electron measurement."""
    prob_error_1: float = 0.005
    """Probability of measuring a 0 instead of 1 in an electron measurement."""

    # single carbon noise
    carbon_init_depolar_prob: float = 0.05
    """Probability of error during carbon initialization."""
    carbon_z_rot_depolar_prob: float = 0.001
    """Probability of error during carbon single gate operation."""

    ec_gate_depolar_prob: float = 0.008
    """Probability of error during native NV two qubit operation between electron and carbon."""

    # coherence times
    electron_T1: float = 1_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds for the electron."""
    electron_T2: float = 300_000_000
    """Dephasing or transverse relaxation time in nanoseconds for the electron."""
    carbon_T1: float = 150_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds for carbon qubits."""
    carbon_T2: float = 1_500_000_000
    """Dephasing or transverse relaxation time in nanoseconds for carbon qubits.."""

    # gate execution times
    carbon_init: float = 310_000
    """Carbon qubit initialization time in nanoseconds."""
    carbon_rot_x: float = 500_000
    """Carbon x rotation gate time in nanoseconds."""
    carbon_rot_y: float = 500_000
    """Carbon y rotation gate time in nanoseconds."""
    carbon_rot_z: float = 500_000
    """Carbon z rotation gate time in nanoseconds."""
    electron_init: float = 2_000
    """Electron qubit initialization time in nanoseconds."""
    electron_rot_x: float = 5
    """Electron x rotation gate time in nanoseconds."""
    electron_rot_y: float = 5
    """Electron y rotation gate time in nanoseconds."""
    electron_rot_z: float = 5
    """Electron z rotation gate time in nanoseconds."""
    ec_controlled_dir_x: float = 500_000
    """Two qubit controlled x rotation gate time in nanoseconds."""
    ec_controlled_dir_y: float = 500_000
    """Two qubit controlled y rotation gate time in nanoseconds."""
    measure: float = 3_700
    """Electron measurement time in nanoseconds."""

    @classmethod
    def from_file(cls, path: str) -> NVQDeviceConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, NVQDeviceConfig)  # type: ignore

    @classmethod
    def perfect_config(cls) -> NVQDeviceConfig:
        """Create a configuration for a device without any noise or errors."""
        # get default config
        cfg = NVQDeviceConfig()

        # set all error params to 0
        cfg.electron_init_depolar_prob = 0
        cfg.electron_single_qubit_depolar_prob = 0
        cfg.prob_error_0 = 0
        cfg.prob_error_1 = 0
        cfg.carbon_init_depolar_prob = 0
        cfg.carbon_z_rot_depolar_prob = 0
        cfg.ec_gate_depolar_prob = 0
        return cfg


class NVQDeviceBuilder(IQDeviceBuilder):
    @classmethod
    def build(cls, name: str, qdevice_cfg: NVQDeviceConfig) -> QuantumProcessor:
        if isinstance(qdevice_cfg, dict):
            qdevice_cfg = NVQDeviceConfig(**qdevice_cfg)

        # noise models for single- and multi-qubit operations
        electron_init_noise = DepolarNoiseModel(
            depolar_rate=qdevice_cfg.electron_init_depolar_prob, time_independent=True
        )

        electron_single_qubit_noise = DepolarNoiseModel(
            depolar_rate=qdevice_cfg.electron_single_qubit_depolar_prob,
            time_independent=True,
        )

        carbon_init_noise = DepolarNoiseModel(
            depolar_rate=qdevice_cfg.carbon_init_depolar_prob, time_independent=True
        )

        carbon_z_rot_noise = DepolarNoiseModel(
            depolar_rate=qdevice_cfg.carbon_z_rot_depolar_prob, time_independent=True
        )

        ec_noise = DepolarNoiseModel(
            depolar_rate=qdevice_cfg.ec_gate_depolar_prob, time_independent=True
        )

        electron_qubit_noise = T1T2NoiseModel(
            T1=qdevice_cfg.electron_T1, T2=qdevice_cfg.electron_T2
        )

        carbon_qubit_noise = T1T2NoiseModel(
            T1=qdevice_cfg.carbon_T1, T2=qdevice_cfg.carbon_T2
        )

        # defining gates and their gate times

        phys_instructions = []

        electron_position = 0
        carbon_positions = [pos + 1 for pos in range(qdevice_cfg.num_qubits - 1)]

        phys_instructions.append(
            PhysicalInstruction(
                INSTR_INIT,
                parallel=False,
                topology=carbon_positions,
                quantum_noise_model=carbon_init_noise,
                apply_q_noise_after=True,
                duration=qdevice_cfg.carbon_init,
            )
        )

        for (instr, dur) in zip(
            [INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z],
            [
                qdevice_cfg.carbon_rot_x,
                qdevice_cfg.carbon_rot_y,
                qdevice_cfg.carbon_rot_z,
            ],
        ):
            phys_instructions.append(
                PhysicalInstruction(
                    instr,
                    parallel=False,
                    topology=carbon_positions,
                    quantum_noise_model=carbon_z_rot_noise,
                    apply_q_noise_after=True,
                    duration=dur,
                )
            )

        phys_instructions.append(
            PhysicalInstruction(
                INSTR_INIT,
                parallel=False,
                topology=[electron_position],
                quantum_noise_model=electron_init_noise,
                apply_q_noise_after=True,
                duration=qdevice_cfg.electron_init,
            )
        )

        for (instr, dur) in zip(
            [INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z],
            [
                qdevice_cfg.electron_rot_x,
                qdevice_cfg.electron_rot_y,
                qdevice_cfg.electron_rot_z,
            ],
        ):
            phys_instructions.append(
                PhysicalInstruction(
                    instr,
                    parallel=False,
                    topology=[electron_position],
                    quantum_noise_model=electron_single_qubit_noise,
                    apply_q_noise_after=True,
                    duration=dur,
                )
            )

        electron_carbon_topologies = [
            (electron_position, carbon_pos) for carbon_pos in carbon_positions
        ]
        phys_instructions.append(
            PhysicalInstruction(
                INSTR_CXDIR,
                parallel=False,
                topology=electron_carbon_topologies,
                quantum_noise_model=ec_noise,
                apply_q_noise_after=True,
                duration=qdevice_cfg.ec_controlled_dir_x,
            )
        )

        phys_instructions.append(
            PhysicalInstruction(
                INSTR_CYDIR,
                parallel=False,
                topology=electron_carbon_topologies,
                quantum_noise_model=ec_noise,
                apply_q_noise_after=True,
                duration=qdevice_cfg.ec_controlled_dir_y,
            )
        )

        M0 = Operator(
            "M0",
            np.diag(
                [
                    np.sqrt(1 - qdevice_cfg.prob_error_0),
                    np.sqrt(qdevice_cfg.prob_error_1),
                ]
            ),
        )
        M1 = Operator(
            "M1",
            np.diag(
                [
                    np.sqrt(qdevice_cfg.prob_error_0),
                    np.sqrt(1 - qdevice_cfg.prob_error_1),
                ]
            ),
        )

        # hack to set imperfect measurements
        INSTR_MEASURE._meas_operators = [M0, M1]

        phys_instr_measure = PhysicalInstruction(
            INSTR_MEASURE,
            parallel=False,
            topology=[electron_position],
            quantum_noise_model=None,
            duration=qdevice_cfg.measure,
        )

        phys_instructions.append(phys_instr_measure)

        # add qubits
        mem_noise_models = [electron_qubit_noise] + [carbon_qubit_noise] * len(
            carbon_positions
        )
        qmem = QuantumProcessor(
            name=name,
            num_positions=qdevice_cfg.num_qubits,
            mem_noise_models=mem_noise_models,
            phys_instructions=phys_instructions,
        )
        return qmem
