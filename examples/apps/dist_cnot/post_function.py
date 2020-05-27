from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(backend):
    # Get the combined state of the qubits after the distributed CNOT.

    app_id = 0
    alice_exec = backend.executioners["alice"]

    # Get Alice's control qubit.
    control_phys_pos = alice_exec._get_position(app_id=app_id, address=1)

    # The `qstate` contains the combined state of control and target.
    combined_state = backend.qmemories["alice"]._get_qubits(control_phys_pos)[0].qstate
    logger.info(f"resulting state = \n{combined_state.ket}")

    return {
        'final_state': combined_state.ket.tolist()
    }
