from dataclasses import dataclass
import numpy as np

from netsquid.components.instructions import (
    INSTR_X, INSTR_Y, INSTR_Z, INSTR_ROT_X,
    INSTR_ROT_Y, INSTR_ROT_Z, INSTR_INIT,
    INSTR_CXDIR, INSTR_CYDIR, INSTR_MEASURE,
)
from netsquid.components.qprocessor import QuantumProcessor
from netsquid.qubits.operators import Operator
from netsquid.components.models.qerrormodels import (
    DepolarNoiseModel,
    T1T2NoiseModel)
from netsquid.components.qprocessor import PhysicalInstruction


@dataclass
class NVConfig:
    # number of qubits per NV
    tot_num_qubits: int

    # initialization error of the electron spin
    electron_init_depolar_prob: float

    # error of the single-qubit gate
    electron_single_qubit_depolar_prob: float

    # measurement errors (prob_error_X is the probability that outcome X is flipped to 1 - X)
    prob_error_0: float
    prob_error_1: float

    # initialization error of the carbon nuclear spin
    carbon_init_depolar_prob: float

    # error of the Z-rotation gate on the carbon nuclear spin
    carbon_z_rot_depolar_prob: float

    # error of the native NV two-qubit gate
    ec_gate_depolar_prob: float

    # coherence times
    electron_T1: int
    electron_T2: int
    carbon_T1: int
    carbon_T2: int


@dataclass
class NVLinkConfig:
    pass


# Build a NVConfig object from a dict that is created by reading a yaml file.
def parse_nv_config(cfg) -> NVConfig:
    try:
        return NVConfig(
            tot_num_qubits=cfg['tot_num_qubits'],
            electron_init_depolar_prob=cfg['electron_init_depolar_prob'],
            electron_single_qubit_depolar_prob=cfg['electron_single_qubit_depolar_prob'],
            prob_error_0=cfg['prob_error_0'],
            prob_error_1=cfg['prob_error_1'],
            carbon_init_depolar_prob=cfg['carbon_init_depolar_prob'],
            carbon_z_rot_depolar_prob=cfg['carbon_z_rot_depolar_prob'],
            ec_gate_depolar_prob=cfg['ec_gate_depolar_prob'],
            electron_T1=cfg['electron_T1'],
            electron_T2=cfg['electron_T2'],
            carbon_T1=cfg['carbon_T1'],
            carbon_T2=cfg['carbon_T2'],
        )
    except KeyError as e:
        raise ValueError(f"Invalid NV configuration: key not found: {e}")


def build_nv_qdevice(name, cfg: NVConfig):

    # noise models for single- and multi-qubit operations
    electron_init_noise = \
        DepolarNoiseModel(depolar_rate=cfg.electron_init_depolar_prob,
                          time_independent=True)

    electron_single_qubit_noise = \
        DepolarNoiseModel(depolar_rate=cfg.electron_single_qubit_depolar_prob,
                          time_independent=True)

    carbon_init_noise = \
        DepolarNoiseModel(depolar_rate=cfg.carbon_init_depolar_prob,
                          time_independent=True)

    carbon_z_rot_noise = \
        DepolarNoiseModel(depolar_rate=cfg.carbon_z_rot_depolar_prob,
                          time_independent=True)

    ec_noise = \
        DepolarNoiseModel(depolar_rate=cfg.ec_gate_depolar_prob,
                          time_independent=True)

    electron_qubit_noise = \
        T1T2NoiseModel(T1=cfg.electron_T1, T2=cfg.electron_T2)

    carbon_qubit_noise = \
        T1T2NoiseModel(T1=cfg.carbon_T1, T2=cfg.carbon_T2)

    # defining gates and their gate times

    phys_instructions = []

    electron_position = 0
    carbon_positions = [pos + 1 for pos in range(cfg.tot_num_qubits - 1)]

    phys_instructions.append(
        PhysicalInstruction(INSTR_INIT,
                            parallel=False,
                            topology=carbon_positions,
                            q_noise_model=carbon_init_noise,
                            apply_q_noise_after=True,
                            duration=310e3))

    for instr in [INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z]:
        phys_instructions.append(
            PhysicalInstruction(instr,
                                parallel=False,
                                topology=carbon_positions,
                                q_noise_model=carbon_z_rot_noise,
                                apply_q_noise_after=True,
                                duration=500e3))

    phys_instructions.append(
        PhysicalInstruction(INSTR_INIT,
                            parallel=False,
                            topology=[electron_position],
                            q_noise_model=electron_init_noise,
                            apply_q_noise_after=True,
                            duration=2e3))

    for instr in [INSTR_X, INSTR_Y, INSTR_Z, INSTR_ROT_X, INSTR_ROT_Y, INSTR_ROT_Z]:
        phys_instructions.append(
            PhysicalInstruction(instr,
                                parallel=False,
                                topology=[electron_position],
                                q_noise_model=electron_single_qubit_noise,
                                duration=5))

    electron_carbon_topologies = \
        [(electron_position, carbon_pos) for carbon_pos in carbon_positions]
    phys_instructions.append(
        PhysicalInstruction(INSTR_CXDIR,
                            parallel=False,
                            topology=electron_carbon_topologies,
                            q_noise_model=ec_noise,
                            apply_q_noise_after=True,
                            duration=500e3))

    phys_instructions.append(
        PhysicalInstruction(INSTR_CYDIR,
                            parallel=False,
                            topology=electron_carbon_topologies,
                            q_noise_model=ec_noise,
                            apply_q_noise_after=True,
                            duration=500e3))

    M0 = Operator("M0", np.diag([np.sqrt(1 - cfg.prob_error_0), np.sqrt(cfg.prob_error_1)]))
    M1 = Operator("M1", np.diag([np.sqrt(cfg.prob_error_0), np.sqrt(1 - cfg.prob_error_1)]))

    # hack to set imperfect measurements
    INSTR_MEASURE._meas_operators = [M0, M1]

    phys_instr_measure = PhysicalInstruction(INSTR_MEASURE,
                                             parallel=False,
                                             topology=[electron_position],
                                             q_noise_model=None,
                                             duration=3.7e3)

    phys_instructions.append(phys_instr_measure)

    # add qubits
    mem_noise_models = [electron_qubit_noise] + \
                       [carbon_qubit_noise] * len(carbon_positions)
    qmem = QuantumProcessor(name=name,
                            num_positions=cfg.tot_num_qubits,
                            mem_noise_models=mem_noise_models,
                            phys_instructions=phys_instructions)
    qmem._fail_exception = True
    return qmem
