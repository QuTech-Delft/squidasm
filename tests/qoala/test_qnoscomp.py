from __future__ import annotations

from netsquid.nodes import Node

from squidasm.qoala.sim.qnoscomp import QnosComponent


def create_qnoscomp() -> QnosComponent:
    node = Node(name="alice", ID=0)
    return QnosComponent(node)


def test_ports():
    comp = create_qnoscomp()

    assert len(comp.ports) == 6
    assert "host_in" in comp.ports
    assert "host_out" in comp.ports
    assert "nstk_in" in comp.ports
    assert "nstk_out" in comp.ports
    assert "nstk_mem_in" in comp.ports
    assert "nstk_mem_out" in comp.ports


if __name__ == "__main__":
    test_ports()
