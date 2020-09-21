from netsquid.qubits import qubitapi as qapi

from squidasm.backend.glob import get_running_backend


def get_qubit_state(qubit, reduced_dm=True):
    """Get the state of the qubit, only possible in simulation and can be used for debugging.

    .. note:: The function gets the *current* state of the qubit. So make sure the the subroutine is flushed
              before calling the method.

    Parameters
    ----------
    qubit : :class:`~netqasm.sdk.qubit.Qubit`
        The qubit to get the state of.
    reduced_dm : bool
        If `True` then a single-qubit state is returned which is the reduced density matrix of the qubit,
        after taking partial trace of any other qubit.
        Otherwise the full state of the qubit is returned (also as dm).

    Returns
    -------
    np.array
        The state as a density matrix.
    """
    # Get the executioner and qmemory from the backend
    backend = get_running_backend()
    node_name = qubit._conn.name
    assert node_name in backend.nodes, f"Unknown node {node_name}"
    executioner = backend.executioners[node_name]
    qmemory = backend.qmemories[node_name]

    # Get the physical position of the qubit
    virtual_address = qubit.qubit_id
    app_id = qubit._conn.app_id
    phys_pos = executioner._get_position(address=virtual_address, app_id=app_id)

    # Get the netsquid qubit
    ns_qubit = qmemory.mem_positions[phys_pos].get_qubit()

    if reduced_dm:
        dm = qapi.reduced_dm(ns_qubit)
    else:
        dm = ns_qubit.qstate.dm

    return dm
