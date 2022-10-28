from squidasm.qoala.sim.memory import (
    CommQubitTrait,
    MemQubitTrait,
    Topology,
    UnitModule,
)


def test_create_unit_module():
    um = UnitModule.from_topology(Topology(comm_ids={0}, mem_ids={0}))
    assert um == UnitModule(
        qubit_ids=[0], qubit_traits={0: [CommQubitTrait, MemQubitTrait]}, gate_traits={}
    )

    um2 = UnitModule.from_topology(Topology(comm_ids={0}, mem_ids={1, 2}))
    assert um2 == UnitModule(
        qubit_ids=[0, 1, 2],
        qubit_traits={0: [CommQubitTrait], 1: [MemQubitTrait], 2: [MemQubitTrait]},
        gate_traits={},
    )


if __name__ == "__main__":
    test_create_unit_module()
