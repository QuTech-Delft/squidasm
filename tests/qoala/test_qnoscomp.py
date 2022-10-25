from __future__ import annotations

from typing import Generator, List, Optional, Tuple

import netsquid as ns
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import (
    GlobalEnvironment,
    GlobalNodeInfo,
    LocalEnvironment,
)
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.util.tests import yield_from


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
