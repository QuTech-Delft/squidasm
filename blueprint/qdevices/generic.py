from __future__ import annotations

from netsquid.components.instructions import (
    INSTR_CNOT,
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

from blueprint.yaml_loadable import YamlLoadable


class GenericQDeviceConfig(YamlLoadable):
    """
    The configuration for a generic quantum device.
    """

    num_qubits: int = 2
    """Number of qubits in the quantum device."""
    num_comm_qubits: int = 2
    """Number of communication qubits. Not used."""

    # coherence times (same for each qubit)
    T1: float = 10_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds."""
    T2: float = 1_000_000_000
    """Dephasing or transverse relaxation time in nanoseconds."""

    # gate execution times
    init_time: float = 10_000
    """Qubit initialization time in nanoseconds."""
    single_qubit_gate_time: float = 1_000
    """Single qubit gate execution time in nanoseconds."""
    two_qubit_gate_time: float = 100_000
    """Two qubit gate execution time in nanoseconds."""
    measure_time: float = 10_000
    """Qubit measurement time in nanoseconds."""

    # noise model
    single_qubit_gate_depolar_prob: float = 0.0
    """Probability of error in each single qubit gate operation. """
    two_qubit_gate_depolar_prob: float = 0.01
    """Probability of error in each two qubit gate operation."""

    @classmethod
    def perfect_config(cls) -> GenericQDeviceConfig:
        """Create a configuration for a device without any noise or errors."""
        cfg = GenericQDeviceConfig()
        cfg.init_time = 0
        cfg.single_qubit_gate_depolar_prob = 0
        cfg.two_qubit_gate_depolar_prob = 0
        cfg.measure_time = 0
        cfg.single_qubit_gate_depolar_prob = 0.0
        cfg.two_qubit_gate_depolar_prob = 0.0
        return cfg


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