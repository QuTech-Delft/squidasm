import numpy
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.ketstates import bell_states


def calculate_fidelity_epr(dm_epr_state: numpy.ndarray, bell_state: int):
    ref_qubit = qapi.create_qubits(2, "reference")
    qapi.assign_qstate(ref_qubit, dm_epr_state)
    fid = qapi.fidelity(ref_qubit, bell_states[bell_state], squared=True)
    return fid


def fidelity_to_prob_max_mixed(fid: float) -> float:
    """Calculate the probability of a state being maximally mixed given a probability.
    Only applicable in two qubit systems and if the only noise is depolarising noise.
    """
    return (1 - fid) * 4.0 / 3.0


def prob_max_mixed_to_fidelity(prob: float) -> float:
    """Calculate the fidelity given the probability of a state being maximally.
    Only applicable in two qubit systems and if the only noise is depolarising noise.
    """
    return 1 - prob * 3.0 / 4.0
