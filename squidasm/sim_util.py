from netsquid.qubits import qubitapi as qapi

from netqasm.sdk.qubit import Qubit

from squidasm.backend.glob import get_running_backend


def get_qubit_state(qubit, reduced_dm=True):
    """Get the state of the qubit(s), only possible in simulation and can be used for debugging.

    .. note:: The function gets the *current* state of the qubit(s). So make sure the the subroutine is flushed
              before calling the method.

    Parameters
    ----------
    qubit : :class:`~netqasm.sdk.qubit.Qubit` or list
        The qubit to get the state of or list of qubits.
    reduced_dm : bool
        If `True` then a single-qubit state is returned which is the reduced density matrix of the qubit,
        after taking partial trace of any other qubit.
        Otherwise the full state of the qubit is returned (also as dm).

    Returns
    -------
    np.array
        The state as a density matrix.
    """
    if isinstance(qubit, Qubit):
        qubits = [qubit]
    else:
        qubits = list(qubit)
    # Get the executioner and qmemory from the backend
    backend = get_running_backend()
    ns_qubits = []
    for q in qubits:
        node_name = q._conn.node_name
        assert node_name in backend.nodes, f"Unknown node {node_name}"
        executioner = backend.executioners[node_name]
        qmemory = backend.qmemories[node_name]

        # Get the physical position of the qubit
        virtual_address = q.qubit_id
        app_id = q._conn.app_id
        phys_pos = executioner._get_position(address=virtual_address, app_id=app_id)

        # Get the netsquid qubit
        ns_qubit = qmemory.mem_positions[phys_pos].get_qubit()
        ns_qubits.append(ns_qubit)

    if reduced_dm:
        dm = qapi.reduced_dm(ns_qubits)
    else:
        if len(qubits) != 1:
            raise ValueError("Getting the state of multiple qubits with `reduced_dm=False` is not allowed "
                             "since it can require merging the states")
        dm = ns_qubits[0].qstate.dm

    return dm
