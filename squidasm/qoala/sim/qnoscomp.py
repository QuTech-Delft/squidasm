from __future__ import annotations

from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from squidasm.qoala.runtime.environment import GlobalEnvironment


class QnosComponent(Component):
    """NetSquid component representing a QNodeOS instance.

    Subcomponent of a ProcNodeComponent.

    This is a static container for QNodeOS-related components and ports.
    Behavior of a QNodeOS instance is modeled in the `Qnos` class,
    which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node) -> None:
        super().__init__(name=f"{node.name}_qnos")
        self._node = node

        # Ports for communicating with Host
        self.add_ports(["host_out", "host_in"])
        self.add_ports(["nstk_out", "nstk_in"])

    @property
    def host_in_port(self) -> Port:
        return self.ports["host_in"]

    @property
    def netstack_out_port(self) -> Port:
        return self.ports["nstk_out"]

    @property
    def netstack_in_port(self) -> Port:
        return self.ports["nstk_in"]

    @property
    def host_out_port(self) -> Port:
        return self.ports["host_out"]

    @property
    def node(self) -> Node:
        return self._node
