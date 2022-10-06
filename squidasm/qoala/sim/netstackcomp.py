from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, Generator, List, Optional

from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.runtime.environment import GlobalEnvironment


class NetstackComponent(Component):
    """NetSquid component representing the network stack in QNodeOS.

    Subcomponent of a QnosComponent.

    Has communications ports with
     - the processor component of this QNodeOS
     - the netstack compmonent of the remote node
        NOTE: at this moment only a single other node is supported in the network

    This is a static container for network-stack-related components and ports.
    Behavior of a QNodeOS network stack is modeled in the `NetProcNode` class,
    which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node, global_env: GlobalEnvironment) -> None:
        super().__init__(f"{node.name}_netstack")
        self._node = node
        self.add_ports(["qnos_out", "qnos_in"])

        self._peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._peer_out_ports: Dict[str, str] = {}  # peer name -> port name

        for node in global_env.get_nodes().values():
            port_in_name = f"peer_{node.name}_in"
            port_out_name = f"peer_{node.name}_out"
            self._peer_in_ports[node.name] = port_in_name
            self._peer_out_ports[node.name] = port_out_name

        self.add_ports(self._peer_in_ports.values())
        self.add_ports(self._peer_out_ports.values())

    @property
    def qnos_in_port(self) -> Port:
        return self.ports["qnos_in"]

    @property
    def qnos_out_port(self) -> Port:
        return self.ports["qnos_out"]

    def peer_in_port(self, name: str) -> Port:
        port_name = self._peer_in_ports[name]
        return self.ports[port_name]

    def peer_out_port(self, name: str) -> Port:
        port_name = self._peer_out_ports[name]
        return self.ports[port_name]

    @property
    def node(self) -> Node:
        return self._node
