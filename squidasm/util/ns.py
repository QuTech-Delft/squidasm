from typing import Optional
from itertools import product

import numpy as np
from numpy import linalg, ndarray

from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.qstate import QState


def is_dm_pure(dm: ndarray, tol: Optional[float] = None) -> bool:
    """Checks if a state is pure not not"""
    rank = linalg.matrix_rank(dm, tol=tol)
    return bool(rank == 1)


def is_state_entangled(state: QState, tol: Optional[float] = None) -> Optional[bool]:
    """ Checks if a arbitrary qubit state is entangled.
    If a decision cannot be made, `None` is returned.
    Decision will always be made for

    * Number of qubits <= 2
    * Pure states

    """
    if state.num_qubits <= 1:
        return False
    if is_dm_pure(dm=state.dm, tol=tol):
        return is_pure_state_entangled(state=state, tol=tol)
    if state.num_qubits == 2:
        return not is_ppt(mat=state.dm)
    else:
        # Not implemented to decide if multipartite states are entangled in general
        return None


def is_pure_state_entangled(state: QState, tol: Optional[float] = None) -> bool:
    """Checks if a pure qubit state is entangled by checking the reduced
    state of each qubit. If any of the reduced state is mixed then the state
    is entangled and `True` is returned, otherwise `False`.
    """
    for qubit in state.qubits:
        reduced_dm = qapi.reduced_dm(qubit)
        if not is_dm_pure(dm=reduced_dm, tol=tol):
            return True
    return False


def partial_transpose(mat: ndarray, dim: int = 2, size_b: Optional[int] = None) -> ndarray:
    """Takes the partial transpose of second half of the system.
    It is assumed that the matrix `mat` is of dimension `dim^(n+m) x dim^(n+m)`.
    Where `m` is given by `size_b` and `dim` is by default 2.
    If `size_b` is not given (default) then it is assumed that `n = m`.
    The partial transpose is then taken over the second `dim^m x dim^m` system.
    """
    # Find n and m
    nrows = mat.shape[0]
    ncols = mat.shape[1]
    assert nrows == ncols, "Not a square matrix ({nrows} != {ncols})"
    exponent = int(np.log(nrows) / np.log(dim))
    assert dim ** exponent == nrows, f"Number of rows ({nrows}) not a power of {dim}"
    if size_b is None:
        n = m = exponent // 2
        assert n + m == exponent, (f"Number of rows ({nrows}) not {dim}^x where x is a "
                                   f"even number, consider setting `size_b`")
    else:
        n = exponent - m
        assert n + m == exponent, f"Number of rows ({nrows}) not {dim}^x where x is divisible by {size_b}"

    # Extract all dim^m x dim^m sub matrices
    N = dim ** n
    M = dim ** m
    submats = [[None] * N for _ in range(N)]
    for j, k in product(range(N), repeat=2):
        # Transpose each submatrix
        submats[j][k] = mat[M*j:M*(j+1), N*k:N*(k+1)].transpose()
    return np.block(submats)


def is_ppt(mat: ndarray, dim: int = 2, size_b: Optional[int] = None) -> bool:
    """Checks if a matrix satisfy the ppt condition (https://en.wikipedia.org/wiki/Peres%E2%80%93Horodecki_criterion)
    Inputs are the same as for :func:`~.partial_transpose`.
    """
    pt_mat = partial_transpose(mat=mat, dim=dim, size_b=size_b)
    return np.all(linalg.eigvals(pt_mat) >= 0)
