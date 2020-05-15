from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(backend):
    app_id = 0
    node_name = "bob"
    executioner = backend.executioners[node_name]
    phys_pos = executioner._get_position(app_id=app_id, address=0)
    state = backend.qmemories[node_name]._get_qubits(phys_pos)[0].qstate.dm
    logger.info(f"state = {state}")
    return {
        "state": state.tolist(),
    }
