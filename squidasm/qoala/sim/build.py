import numpy as np
from netsquid.components.instructions import (
    INSTR_CNOT,
    INSTR_CXDIR,
    INSTR_CYDIR,
    INSTR_CZ,
    INSTR_H,
    INSTR_INIT,
    INSTR_MEASURE,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_X,
    INSTR_Y,
    INSTR_Z,
)
from netsquid.components.models.qerrormodels import DepolarNoiseModel, T1T2NoiseModel
from netsquid.components.qprocessor import PhysicalInstruction, QuantumProcessor
from netsquid.qubits.operators import Operator

from squidasm.run.stack.config import GenericQDeviceConfig, NVQDeviceConfig


def build_generic_qdevice(name: str, cfg: GenericQDeviceConfig) -> QuantumProcessor:
    phys_instructions = []

    single_qubit_gate_noise = DepolarNoiseModel(
        depolar_rate=cfg.single_qubit_gate_depolar_prob, time_independent=True
    )

    two_qubit_gate_noise = DepolarNoiseModel(
        depolar_rate=cfg.two_qubit_gate_depolar_prob, time_independent=True
    )

    phys_instructions.append(
        PhysicalInstruction(
            INSTR_INIT,
            parallel=False,
            duration=cfg.init_time,
        )
    )

    for instr in [
        INSTR_ROT_X,
        INSTR_ROT_Y,
        INSTR_ROT_Z,
        INSTR_X,
        INSTR_Y,
        INSTR_Z,
        INSTR_H,
    ]:
        phys_instructions.append(
            PhysicalInstruction(
                instr,
                parallel=False,
                quantum_noise_model=single_qubit_gate_noise,
                apply_q_noise_after=True,
                duration=cfg.single_qubit_gate_time,
            )
        )

    for instr in [INSTR_CNOT, INSTR_CZ]:
        phys_instructions.append(
            PhysicalInstruction(
                instr,
                parallel=False,
                quantum_noise_model=two_qubit_gate_noise,
                apply_q_noise_after=True,
                duration=cfg.two_qubit_gate_time,
            )
        )

    phys_instr_measure = PhysicalInstruction(
        INSTR_MEASURE,
        parallel=False,
        duration=cfg.measure_time,
    )
    phys_instructions.append(phys_instr_measure)

    electron_qubit_noise = T1T2NoiseModel(T1=cfg.T1, T2=cfg.T2)
    mem_noise_models = [electron_qubit_noise] * cfg.num_qubits
    qmem = QuantumProcessor(
        name=name,
        num_positions=cfg.num_qubits,
        mem_noise_models=mem_noise_models,
        phys_instructions=phys_instructions,
    )
    return qmem


def build_nv_qdevice(name: str, cfg: NVQDeviceConfig) -> QuantumProcessor:

    # noise models for single- and multi-qubit operations
    electron_init_noise = DepolarNoiseModel(
        depolar_rate=cfg.electron_init_depolar_prob, time_independent=True
    )

    electron_single_qubit_noise = DepolarNoiseModel(
        depolar_rate=cfg.electron_single_qubit_depolar_prob, time_independent=True
    )

    carbon_init_noise = DepolarNoiseModel(
        depolar_rate=cfg.carbon_init_depolar_prob, time_independent=True
    )

    carbon_z_rot_noise = DepolarNoiseModel(
        depolar_rate=cfg.carbon_z_rot_depolar_prob, time_independent=True
    )

    ec_noise = DepolarNoiseModel(
        depolar_rate=cfg.ec_gate_depolar_prob, time_independent=True
    )

    electron_qubit_noise = T1T2NoiseModel(T1=cfg.electron_T1, T2=cfg.electron_T2)

    carbon_qubit_noise = T1T2NoiseModel(T1=cfg.carbon_T1, T2=cfg.carbon_T2)

    # defining gates and their gate times

    phys_instructions = []

    electron_position = 0
    carbon_positions = [pos + 1 for pos in range(cfg.num_qubits - 1)]

    phys_instructions.append(
        PhysicalInstruction(
            INSTR_INIT,
            parallel=False,
            topology=carbon_positions,
            quantum_noise_model=carbon_init_noise,
            apply_q_noise_after=True,
            duration=cfg.carbon_init,
        )
    )

    for (instr, dur) in zip(
        [INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z],
        [cfg.carbon_rot_x, cfg.carbon_rot_y, cfg.carbon_rot_z],
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
            duration=cfg.electron_init,
        )
    )

    for (instr, dur) in zip(
        [INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z],
        [cfg.electron_rot_x, cfg.electron_rot_y, cfg.electron_rot_z],
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
            duration=cfg.ec_controlled_dir_x,
        )
    )

    phys_instructions.append(
        PhysicalInstruction(
            INSTR_CYDIR,
            parallel=False,
            topology=electron_carbon_topologies,
            quantum_noise_model=ec_noise,
            apply_q_noise_after=True,
            duration=cfg.ec_controlled_dir_y,
        )
    )

    M0 = Operator(
        "M0", np.diag([np.sqrt(1 - cfg.prob_error_0), np.sqrt(cfg.prob_error_1)])
    )
    M1 = Operator(
        "M1", np.diag([np.sqrt(cfg.prob_error_0), np.sqrt(1 - cfg.prob_error_1)])
    )

    # hack to set imperfect measurements
    INSTR_MEASURE._meas_operators = [M0, M1]

    phys_instr_measure = PhysicalInstruction(
        INSTR_MEASURE,
        parallel=False,
        topology=[electron_position],
        quantum_noise_model=None,
        duration=cfg.measure,
    )

    phys_instructions.append(phys_instr_measure)

    # add qubits
    mem_noise_models = [electron_qubit_noise] + [carbon_qubit_noise] * len(
        carbon_positions
    )
    qmem = QuantumProcessor(
        name=name,
        num_positions=cfg.num_qubits,
        mem_noise_models=mem_noise_models,
        phys_instructions=phys_instructions,
    )
    return qmem
