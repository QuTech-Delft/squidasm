from __future__ import annotations

from typing import Generator

import netsquid as ns
from netsquid.nodes import Node
from netsquid.protocols import Protocol

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import (
    GlobalEnvironment,
    GlobalNodeInfo,
    LocalEnvironment,
)
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.procnodecomp import ProcNodeComponent


def create_procnodecomp(num_other_nodes: int) -> ProcNodeComponent:
    env = GlobalEnvironment()

    node_info = GlobalNodeInfo.default_nv("alice", 0, 2)
    env.add_node(0, node_info)

    for id in range(1, num_other_nodes + 1):
        node_info = GlobalNodeInfo.default_nv(f"node_{id}", id, 2)
        env.add_node(id, node_info)

    return ProcNodeComponent(name="alice", qprocessor=None, global_env=env)


def test_no_other_nodes():
    comp = create_procnodecomp(num_other_nodes=0)

    # should not have any ports
    assert len(comp.ports) == 0


def test_one_other_node():
    comp = create_procnodecomp(num_other_nodes=1)

    # should have 2 host peer ports + 2 netstack peer ports
    assert len(comp.ports) == 4
    assert "host_peer_node_1_in" in comp.ports
    assert "host_peer_node_1_out" in comp.ports
    assert "netstack_peer_node_1_in" in comp.ports
    assert "netstack_peer_node_1_out" in comp.ports

    # Test properties
    assert comp.host_peer_in_port("node_1") == comp.ports["host_peer_node_1_in"]
    assert comp.host_peer_out_port("node_1") == comp.ports["host_peer_node_1_out"]
    assert comp.netstack_peer_in_port("node_1") == comp.ports["netstack_peer_node_1_in"]
    assert (
        comp.netstack_peer_out_port("node_1") == comp.ports["netstack_peer_node_1_out"]
    )


def test_many_other_nodes():
    comp = create_procnodecomp(num_other_nodes=5)

    # should 5 * 4 peer ports
    assert len(comp.ports) == 20

    for i in range(1, 6):
        assert f"host_peer_node_{i}_in" in comp.ports
        assert f"host_peer_node_{i}_out" in comp.ports
        assert f"netstack_peer_node_{i}_in" in comp.ports
        assert f"netstack_peer_node_{i}_out" in comp.ports
        # Test properties
        assert (
            comp.host_peer_in_port(f"node_{i}") == comp.ports[f"host_peer_node_{i}_in"]
        )
        assert (
            comp.host_peer_out_port(f"node_{i}")
            == comp.ports[f"host_peer_node_{i}_out"]
        )
        assert (
            comp.netstack_peer_in_port(f"node_{i}")
            == comp.ports[f"netstack_peer_node_{i}_in"]
        )
        assert (
            comp.netstack_peer_out_port(f"node_{i}")
            == comp.ports[f"netstack_peer_node_{i}_out"]
        )


if __name__ == "__main__":
    test_no_other_nodes()
    test_one_other_node()
    test_many_other_nodes()
