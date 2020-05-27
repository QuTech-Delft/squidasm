import netsquid as ns
from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(backend):
    app_id = 0

    alice_exec = backend.executioners["alice"]
    control_phys_pos = alice_exec._get_position(app_id=app_id, address=1)
    control_state = backend.qmemories["alice"]._get_qubits(control_phys_pos)[0].qstate
    logger.info(f"control = \n{control_state.dm}")

    bob_exec = backend.executioners["bob"]
    target_phys_pos = bob_exec._get_position(app_id=app_id, address=1)
    target_state = backend.qmemories["bob"]._get_qubits(target_phys_pos)[0].qstate
    logger.info(f"target = \n{target_state.dm}")

