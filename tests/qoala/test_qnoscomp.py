from __future__ import annotations

from netsquid.nodes import Node

from squidasm.qoala.runtime.environment import GlobalEnvironment, GlobalNodeInfo
from squidasm.qoala.sim.qnoscomp import QnosComponent


def create_qnoscomp() -> QnosComponent:
    node = Node(name="alice", ID=0)
    env = GlobalEnvironment()

    node_info = GlobalNodeInfo.default_nv(node.name, node.ID, 2)
    env.add_node(node.ID, node_info)

    return QnosComponent(node, env)


def test_ports():
    comp = create_qnoscomp()

    # should have host_in, host_out, nstk_in and nstk_out port
    assert len(comp.ports) == 4
    assert "host_in" in comp.ports
    assert "host_out" in comp.ports
    assert "nstk_in" in comp.ports
    assert "nstk_out" in comp.ports


if __name__ == "__main__":
    test_ports()
