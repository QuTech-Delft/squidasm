from squidasm.qoala.sim.memory import CommQubitTrait, UnitModule


def default_nv_unit_module(num_qubits: int) -> UnitModule():
    return UnitModule(
        qubit_ids=[i for i in range(num_qubits)],
        qubit_traits={0: CommQubitTrait},
        gate_traits={},
    )
