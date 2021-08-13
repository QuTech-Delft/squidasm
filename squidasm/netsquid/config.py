from dataclasses import dataclass
from typing import Dict

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


@dataclass
class QDeviceConfig:
    # number of qubits per NV
    tot_num_qubits: int = 2

    # initialization error of the electron spin
    electron_init_depolar_prob: float = 0.05

    # error of the single-qubit gate
    electron_single_qubit_depolar_prob: float = 0.0

    # measurement errors (prob_error_X is the probability that outcome X is flipped to 1 - X)
    prob_error_0: float = 0.05
    prob_error_1: float = 0.005

    # initialization error of the carbon nuclear spin
    carbon_init_depolar_prob: float = 0.05

    # error of the Z-rotation gate on the carbon nuclear spin
    carbon_z_rot_depolar_prob: float = 0.001

    # error of the native NV two-qubit gate
    ec_gate_depolar_prob: float = 0.008

    # coherence times
    electron_T1: int = 1_000_000_000
    electron_T2: int = 300_000_000
    carbon_T1: int = 150_000_000_000
    carbon_T2: int = 1_500_000_000

    # gate execution times
    carbon_init: int = 310_000
    carbon_rot_x: int = 500_000
    carbon_rot_y: int = 500_000
    carbon_rot_z: int = 500_000
    electron_init: int = 2_000
    electron_rot_x: int = 5
    electron_rot_y: int = 5
    electron_rot_z: int = 5
    ec_controlled_dir_x: int = 500_000
    ec_controlled_dir_y: int = 500_000
    measure: int = 3_700


def perfect_nv_config() -> QDeviceConfig:
    # get default config
    cfg = QDeviceConfig()

    # set all error params to 0
    cfg.electron_init_depolar_prob = 0
    cfg.electron_single_qubit_depolar_prob = 0
    cfg.prob_error_0 = 0
    cfg.prob_error_1 = 0
    cfg.carbon_init_depolar_prob = 0
    cfg.carbon_z_rot_depolar_prob = 0
    cfg.ec_gate_depolar_prob = 0
    return cfg


def build_nv_qdevice(name: str, cfg: QDeviceConfig) -> QuantumProcessor:

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
    carbon_positions = [pos + 1 for pos in range(cfg.tot_num_qubits - 1)]

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
        num_positions=cfg.tot_num_qubits,
        mem_noise_models=mem_noise_models,
        phys_instructions=phys_instructions,
    )
    return qmem


def parse_nv_config(cfg: Dict) -> QDeviceConfig:
    try:
        return QDeviceConfig(
            tot_num_qubits=cfg["tot_num_qubits"],
            electron_init_depolar_prob=cfg["electron_init_depolar_prob"],
            electron_single_qubit_depolar_prob=cfg[
                "electron_single_qubit_depolar_prob"
            ],
            prob_error_0=cfg["prob_error_0"],
            prob_error_1=cfg["prob_error_1"],
            carbon_init_depolar_prob=cfg["carbon_init_depolar_prob"],
            carbon_z_rot_depolar_prob=cfg["carbon_z_rot_depolar_prob"],
            ec_gate_depolar_prob=cfg["ec_gate_depolar_prob"],
            electron_T1=cfg["electron_T1"],
            electron_T2=cfg["electron_T2"],
            carbon_T1=cfg["carbon_T1"],
            carbon_T2=cfg["carbon_T2"],
            carbon_init=cfg["carbon_init"],
            carbon_rot_x=cfg["carbon_rot_x"],
            carbon_rot_y=cfg["carbon_rot_y"],
            carbon_rot_z=cfg["carbon_rot_z"],
            electron_init=cfg["electron_init"],
            electron_rot_x=cfg["electron_rot_x"],
            electron_rot_y=cfg["electron_rot_y"],
            electron_rot_z=cfg["electron_rot_z"],
            ec_controlled_dir_x=cfg["ec_controlled_dir_x"],
            ec_controlled_dir_y=cfg["ec_controlled_dir_y"],
            measure=cfg["measure"],
        )
    except KeyError as e:
        raise ValueError(f"Invalid NV configuration: key not found: {e}")
