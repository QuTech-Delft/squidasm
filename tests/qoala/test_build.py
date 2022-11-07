import pytest
from netsquid.components.instructions import (
    INSTR_CNOT,
    INSTR_CXDIR,
    INSTR_INIT,
    INSTR_MEASURE,
    INSTR_ROT_X,
    INSTR_X,
)
from netsquid.components.qprocessor import MissingInstructionError, QuantumProcessor

from squidasm.qoala.runtime.config import GenericQDeviceConfig, NVQDeviceConfig
from squidasm.qoala.sim.build import build_generic_qprocessor, build_nv_qprocessor


def test_build_generic_perfect():
    num_qubits = 2
    cfg = GenericQDeviceConfig.perfect_config(num_qubits)
    proc: QuantumProcessor = build_generic_qprocessor(name="alice", cfg=cfg)
    assert proc.num_positions == num_qubits

    for i in range(num_qubits):
        assert proc.get_instruction_duration(INSTR_INIT, [i]) == cfg.init_time
        assert proc.get_instruction_duration(INSTR_MEASURE, [i]) == cfg.measure_time
        assert proc.get_instruction_duration(INSTR_X, [i]) == cfg.single_qubit_gate_time
        assert (
            proc.get_instruction_duration(INSTR_ROT_X, [i])
            == cfg.single_qubit_gate_time
        )

    assert proc.get_instruction_duration(INSTR_CNOT, [0, 1]) == cfg.two_qubit_gate_time

    # TODO: check topology??!


def test_build_nv_perfect():
    num_qubits = 2
    cfg = NVQDeviceConfig.perfect_config(num_qubits)
    proc: QuantumProcessor = build_nv_qprocessor(name="alice", cfg=cfg)
    assert proc.num_positions == num_qubits

    assert proc.get_instruction_duration(INSTR_INIT, [0]) == cfg.electron_init
    assert proc.get_instruction_duration(INSTR_MEASURE, [0]) == cfg.measure
    assert proc.get_instruction_duration(INSTR_ROT_X, [0]) == cfg.electron_rot_x

    for i in range(1, num_qubits):
        assert proc.get_instruction_duration(INSTR_INIT, [i]) == cfg.carbon_init
        assert proc.get_instruction_duration(INSTR_ROT_X, [i]) == cfg.carbon_rot_x
        with pytest.raises(MissingInstructionError):
            assert proc.get_instruction_duration(INSTR_MEASURE, [i])

    with pytest.raises(MissingInstructionError):
        proc.get_instruction_duration(INSTR_CNOT, [0, 1])
        proc.get_instruction_duration(INSTR_CXDIR, [1, 0])

    assert proc.get_instruction_duration(INSTR_CXDIR, [0, 1]) == cfg.ec_controlled_dir_x


if __name__ == "__main__":
    test_build_generic_perfect()
    test_build_nv_perfect()
