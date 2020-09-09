import pytest

import numpy as np

import netsquid as ns
from netsquid.qubits import qubitapi as qapi

from squidasm.ns_util import is_state_entangled, partial_transpose


f = 1 / np.sqrt(2)


@pytest.mark.parametrize('mat, num_qubits, tol, expected', [
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

    # Mixed
    # |00><00|
    (np.array([[1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]), 2, None, False),
    # Maximally mixed
    (np.eye(4), 2, None, False),
    # Perfect Bell pair
    (np.array([[0.5, 0, 0, 0.5], [0, 0, 0, 0], [0, 0, 0, 0], [0.5, 0, 0, 0.5]]), 2, None, True),
    # noisy |00><00|
    (np.array([[0.7, 0, 0, 0], [0, 0.1, 0, 0], [0, 0, 0.1, 0], [0, 0, 0, 0.1]]), 2, None, False),
    # Noisy Bell pair
    (np.array([[0.4, 0, 0, 0.4], [0, 0.1, 0.1, 0], [0, 0.1, 0.1, 0], [0.4, 0, 0, 0.4]]), 2, None, True),

])
def test_is_state_entangled(mat, num_qubits, tol, expected):
    ns.set_qstate_formalism(ns.QFormalism.DM)
    qubits = qapi.create_qubits(num_qubits)
    qapi.assign_qstate(qubits, mat)
    assert is_state_entangled(qubits[0].qstate, tol=tol) == expected


@pytest.mark.parametrize("mat, expected", [
    (np.eye(4), np.eye(4)),
    (
        np.array([
            [1, 0, 0, 1],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [1, 0, 0, 1],
        ]),
        np.array([
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
        ]),
    ),
    (
        np.array([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, 16],
        ]),
        np.array([
            [1, 5, 3, 7],
            [2, 6, 4, 8],
            [9, 13, 11, 15],
            [10, 14, 12, 16],
        ]),
    ),
])
def test_partial_transpose(mat, expected):
    print(mat)
    pt_mat = partial_transpose(mat)
    print(pt_mat)
    assert np.all(np.isclose(pt_mat, expected))
