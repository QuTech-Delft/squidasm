from numpy import linalg

import netsquid as ns
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.qubit import Qubit


def is_qubit_entangled(qubit, tol=None):
    if not isinstance(qubit, Qubit):
        raise TypeError(f"Excepted Qubit not {type(qubit)}")
    if not ns.get_qstate_formalism() == ns.QFormalism.KET:
        raise NotImplementedError
    dm = qapi.reduced_dm(qubit)
    rank = linalg.matrix_rank(dm, tol=tol)
    return bool(rank > 1)
