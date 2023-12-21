import numpy
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.ketstates import bell_states


def calculate_fidelity_epr(dm_epr_state: numpy.ndarray, bell_state: int):
    ref_qubit = qapi.create_qubits(2, "reference")
    qapi.assign_qstate(ref_qubit, dm_epr_state)
    fid = qapi.fidelity(ref_qubit, bell_states[bell_state], squared=True)
    return fid
