from typing import Generator

import netsquid as ns
import pytest
from netsquid.components import instructions as ns_instr
from netsquid.components.qprocessor import MissingInstructionError, QuantumProcessor
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid.qubits import ketstates, qubitapi

from pydynaa import EventExpression
from squidasm.qoala.runtime.config import GenericQDeviceConfig, NVQDeviceConfig
from squidasm.qoala.sim.build import build_generic_qprocessor, build_nv_qprocessor
from squidasm.qoala.sim.constants import PI, PI_OVER_2
from squidasm.qoala.sim.qdevice import (
    GenericPhysicalQuantumMemory,
    NonInitializedQubitError,
    NVPhysicalQuantumMemory,
    PhysicalQuantumMemory,
    QDevice,
    QDeviceCommand,
    QDeviceType,
    UnsupportedQDeviceCommandError,
)
from squidasm.util.tests import has_state, netsquid_run


def perfect_generic_qdevice(num_qubits: int) -> QDevice:
    cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    processor = build_generic_qprocessor(name="processor", cfg=cfg)
    node = Node(name="alice", qmemory=processor)
    return QDevice(
        node=node,
        typ=QDeviceType.GENERIC,
        memory=GenericPhysicalQuantumMemory(num_qubits),
    )


def perfect_nv_qdevice(num_qubits: int) -> QDevice:
    cfg = NVQDeviceConfig.perfect_config(num_qubits=num_qubits)
    processor = build_nv_qprocessor(name="processor", cfg=cfg)
    node = Node(name="alice", qmemory=processor)
    return QDevice(
        node=node,
        typ=QDeviceType.NV,
        memory=NVPhysicalQuantumMemory(num_qubits),
    )


def test_static_generic():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    assert qdevice.qprocessor.num_positions == num_qubits

    assert qdevice.typ == QDeviceType.GENERIC
    assert qdevice.qubit_count == num_qubits
    assert qdevice.comm_qubit_count == num_qubits
    assert qdevice.comm_qubit_ids == {i for i in range(num_qubits)}
    assert qdevice.mem_qubit_ids == {i for i in range(num_qubits)}
    assert qdevice.all_qubit_ids == {i for i in range(num_qubits)}


def test_static_nv():
    num_qubits = 3
    qdevice = perfect_nv_qdevice(num_qubits)

    assert qdevice.qprocessor.num_positions == num_qubits
    with pytest.raises(MissingInstructionError):
        qdevice.qprocessor.get_instruction_duration(ns_instr.INSTR_CNOT, [0, 1])
        qdevice.qprocessor.get_instruction_duration(ns_instr.INSTR_CXDIR, [1, 0])

    # Should not raise error:
    qdevice.qprocessor.get_instruction_duration(ns_instr.INSTR_CXDIR, [0, 1])

    assert qdevice.typ == QDeviceType.NV
    assert qdevice.qubit_count == num_qubits
    assert qdevice.comm_qubit_count == 1
    assert qdevice.comm_qubit_ids == {0}
    assert qdevice.mem_qubit_ids == {i for i in range(1, num_qubits)}
    assert qdevice.all_qubit_ids == {i for i in range(num_qubits)}


def test_initalize_generic():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    # All qubits are not initalized yet.
    assert qdevice.get_local_qubit(0) is None
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # Initialize qubit 0.
    commands = [QDeviceCommand(ns_instr.INSTR_INIT, [0])]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    # Qubit 0 should be initalized and have state |0>
    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s0)

    commands = [QDeviceCommand(ns_instr.INSTR_X, [0])]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s1)

    # Qubits 1 and 2 are still not initalized.
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # Initialize qubit 1.
    commands = [QDeviceCommand(ns_instr.INSTR_INIT, [1])]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    # Qubit 0 should still be in |1>.
    # Qubit 1 should be in |0>.
    q0 = qdevice.get_local_qubit(0)
    q1 = qdevice.get_local_qubit(1)
    assert has_state(q0, ketstates.s1)
    assert has_state(q1, ketstates.s0)

    # Test getting multiple qubits at the same time.
    [q0, q1, q2] = qdevice.get_local_qubits([0, 1, 2])
    assert has_state(q0, ketstates.s1)
    assert has_state(q1, ketstates.s0)
    assert q2 is None


def test_initalize_nv():
    num_qubits = 3
    qdevice = perfect_nv_qdevice(num_qubits)

    # All qubits are not initalized yet.
    assert qdevice.get_local_qubit(0) is None
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # Initialize qubit 0.
    commands = [QDeviceCommand(ns_instr.INSTR_INIT, [0])]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    # Qubit 0 should be initalized and have state |0>
    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s0)

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_H, [0])]
        netsquid_run(qdevice.execute_commands(commands))
        ns.sim_run()

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_X, [0])]
        netsquid_run(qdevice.execute_commands(commands))
        ns.sim_run()

    commands = [QDeviceCommand(ns_instr.INSTR_ROT_X, [0], angle=PI)]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s1)

    # Qubits 1 and 2 are still not initalized.
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # Initialize qubit 1.
    commands = [QDeviceCommand(ns_instr.INSTR_INIT, [1])]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    # Qubit 0 should still be in |1>.
    # Qubit 1 should be in |0>.
    q0 = qdevice.get_local_qubit(0)
    q1 = qdevice.get_local_qubit(1)
    assert has_state(q0, ketstates.s1)
    assert has_state(q1, ketstates.s0)

    # Test getting multiple qubits at the same time.
    [q0, q1, q2] = qdevice.get_local_qubits([0, 1, 2])
    assert has_state(q0, ketstates.s1)
    assert has_state(q1, ketstates.s0)
    assert q2 is None


def test_rotations_generic():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    # All qubits are not initalized yet.
    assert qdevice.get_local_qubit(0) is None
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # Initialize qubit 0 and do Y-rotation of PI.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [0]),
        QDeviceCommand(ns_instr.INSTR_Y, [0]),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s1)

    # Initialize qubit 1 and do H gate.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [1]),
        QDeviceCommand(ns_instr.INSTR_H, [1]),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q1 = qdevice.get_local_qubit(1)
    assert has_state(q1, ketstates.h0)

    # Initialize qubit 2, do a H gate, and a Z-rotation of PI/2.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [2]),
        QDeviceCommand(ns_instr.INSTR_H, [2]),
        QDeviceCommand(ns_instr.INSTR_ROT_Z, [2], angle=PI_OVER_2),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q2 = qdevice.get_local_qubit(2)
    assert has_state(q2, ketstates.y0)


def test_rotations_nv():
    num_qubits = 3
    qdevice = perfect_nv_qdevice(num_qubits)

    # All qubits are not initalized yet.
    assert qdevice.get_local_qubit(0) is None
    assert qdevice.get_local_qubit(1) is None
    assert qdevice.get_local_qubit(2) is None

    # NV QDevice does not support X-gate.
    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [
            QDeviceCommand(ns_instr.INSTR_INIT, [0]),
            QDeviceCommand(ns_instr.INSTR_X, [0]),
        ]
        netsquid_run(qdevice.execute_commands(commands))
        ns.sim_run()

    # Initialize qubit 0 and do X-rotation of PI.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [0]),
        QDeviceCommand(ns_instr.INSTR_ROT_X, [0], angle=PI),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q0 = qdevice.get_local_qubit(0)
    assert has_state(q0, ketstates.s1)

    # Initialize qubit 1 and do a Y-rotation of PI/2.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [1]),
        QDeviceCommand(ns_instr.INSTR_ROT_Y, [1], angle=PI_OVER_2),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q1 = qdevice.get_local_qubit(1)
    assert has_state(q1, ketstates.h0)

    # Initialize qubit 2, do a Y-rotation of PI/2, and a Z-rotation of PI/2.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [2]),
        QDeviceCommand(ns_instr.INSTR_ROT_Y, [2], angle=PI_OVER_2),
        QDeviceCommand(ns_instr.INSTR_ROT_Z, [2], angle=PI_OVER_2),
    ]
    netsquid_run(qdevice.execute_commands(commands))
    ns.sim_run()

    q2 = qdevice.get_local_qubit(2)
    assert has_state(q2, ketstates.y0)


def test_measure_generic():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    # Initialize qubit 0 and measure it.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [0]),
        QDeviceCommand(ns_instr.INSTR_MEASURE, [0]),
    ]

    # Need to use actual "yield from" (instead of netsquid_run) because we need the
    # NetSquid simulator itself to yield on the "program finish" event:
    # only then the measurement outcome is written to prog['last'].
    meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    q0 = qdevice.get_local_qubit(0)
    # Applying the NetSquid measurement instruction should not discard the qubit.
    # (A QnosProcessor should do this manually!)
    assert q0 is not None
    assert has_state(q0, ketstates.s0)

    assert meas_outcome is not None
    assert meas_outcome == 0

    # Initialize qubit 1, apply X gate, and measure it.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [1]),
        QDeviceCommand(ns_instr.INSTR_X, [1]),
        QDeviceCommand(ns_instr.INSTR_MEASURE, [1]),
    ]

    meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    q1 = qdevice.get_local_qubit(1)
    # Applying the NetSquid measurement instruction should not discard the qubit.
    # (A QnosProcessor should do this manually!)
    assert q1 is not None
    assert has_state(q1, ketstates.s1)

    assert meas_outcome is not None
    assert meas_outcome == 1

    # Measure qubit 0 again.
    commands = [
        QDeviceCommand(ns_instr.INSTR_MEASURE, [0]),
    ]

    meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    q0 = qdevice.get_local_qubit(0)
    assert q0 is not None
    assert has_state(q0, ketstates.s0)

    assert meas_outcome is not None
    assert meas_outcome == 0


def test_measure_nv():
    num_qubits = 3
    qdevice = perfect_nv_qdevice(num_qubits)

    # Initialize qubit 0 and measure it.
    commands = [
        QDeviceCommand(ns_instr.INSTR_INIT, [0]),
        QDeviceCommand(ns_instr.INSTR_MEASURE, [0]),
    ]

    # Need to use actual "yield from" (instead of netsquid_run) because we need the
    # NetSquid simulator itself to yield on the "program finish" event:
    # only then the measurement outcome is written to prog['last'].
    meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    q0 = qdevice.get_local_qubit(0)
    # Applying the NetSquid measurement instruction should not discard the qubit.
    # (A QnosProcessor should do this manually!)
    assert q0 is not None
    assert has_state(q0, ketstates.s0)

    assert meas_outcome is not None
    assert meas_outcome == 0

    # Initialize qubit 1, and try to measure it. Should raise an error since
    # only qubit 0 can be measured.
    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [
            QDeviceCommand(ns_instr.INSTR_INIT, [1]),
            QDeviceCommand(ns_instr.INSTR_MEASURE, [1]),
        ]
        meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    # Measure qubit 0 again.
    commands = [QDeviceCommand(ns_instr.INSTR_MEASURE, [0])]
    meas_outcome = netsquid_run(qdevice.execute_commands(commands))

    q0 = qdevice.get_local_qubit(0)
    assert q0 is not None
    assert has_state(q0, ketstates.s0)

    assert meas_outcome is not None
    assert meas_outcome == 0


def test_unsupported_commands_generic():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_T, [0])]
        netsquid_run(qdevice.execute_commands(commands))


def test_unsupported_commands_nv():
    num_qubits = 3
    qdevice = perfect_nv_qdevice(num_qubits)

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_X, [0])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_Y, [0])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_Z, [0])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_H, [0])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_X, [1])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_MEASURE, [1])]
        netsquid_run(qdevice.execute_commands(commands))

    with pytest.raises(UnsupportedQDeviceCommandError):
        commands = [QDeviceCommand(ns_instr.INSTR_MEASURE, [2])]
        netsquid_run(qdevice.execute_commands(commands))


def test_non_initalized():
    num_qubits = 3
    qdevice = perfect_generic_qdevice(num_qubits)

    with pytest.raises(NonInitializedQubitError):
        commands = [QDeviceCommand(ns_instr.INSTR_X, [0])]
        netsquid_run(qdevice.execute_commands(commands))


if __name__ == "__main__":
    test_static_generic()
    test_static_nv()
    test_initalize_generic()
    test_initalize_nv()
    test_rotations_generic()
    test_rotations_nv()
    test_measure_generic()
    test_measure_nv()
    test_unsupported_commands_generic()
    test_unsupported_commands_nv()
    test_non_initalized()
