import pytest

import numpy as np

import netsquid as ns
from netsquid.qubits import qubitapi as qapi
from squidasm.ns_util import is_qubit_entangled


def test_is_qubit_entangled_dm():
    ns.set_qstate_formalism(ns.QFormalism.DM)
    qubit = qapi.create_qubits(1)[0]
    with pytest.raises(NotImplementedError):
        is_qubit_entangled(qubit)


def test_is_qubit_entangled_stab():
    ns.set_qstate_formalism(ns.QFormalism.STAB)
    qubit = qapi.create_qubits(1)[0]
    with pytest.raises(NotImplementedError):
        is_qubit_entangled(qubit)


@pytest.mark.parametrize('qubit', [
    None,
    np.array(),
])
def test_is_qubit_entangled_type_error(qubit):
    ns.set_qstate_formalism(ns.QFormalism.STAB)
    with pytest.raises(TypeError):
        is_qubit_entangled(qubit)


f = 1 / np.sqrt(2)


@pytest.mark.parametrize('qs_repr, num_qubits, tol, entangled', [
    (np.array([[1], [0]]), 1, None, False),
    (np.array([[f], [f]]), 1, None, False),

    (np.array([[1], [0], [0], [0]]), 2, None, False),
    (np.array([[f], [0], [f], [0]]), 2, None, False),
    (np.array([[f], [f], [0], [0]]), 2, None, False),
    (np.array([[f], [f], [f], [f]]), 2, None, False),

    (np.array([[f], [0], [0], [f]]), 2, None, True),
    (np.array([[0], [f], [f], [0]]), 2, None, True),

    (np.array([[np.sqrt(2 / 3)], [0], [0], [np.sqrt(1 / 3)]]), 2, None, True),

    (np.array([[np.sqrt(1 - 1e-10)], [0], [0], [np.sqrt(1e-10)]]), 2, 1e-9, False),
    (np.array([[np.sqrt(1 - 1e-10)], [0], [0], [np.sqrt(1e-10)]]), 2, 1e-11, True),
    (np.array([[np.sqrt(1 - 1e-10)], [0], [0], [np.sqrt(1e-10)]]), 2, None, True),
])
def test_is_qubit_entangled_ket(qs_repr, num_qubits, tol, entangled):
    ns.set_qstate_formalism(ns.QFormalism.KET)
    qubits = qapi.create_qubits(num_qubits)
    qapi.assign_qstate(qubits, qs_repr)
    assert is_qubit_entangled(qubits[0], tol=tol) == entangled
