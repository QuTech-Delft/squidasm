from __future__ import annotations

from typing import Dict, List, Optional

from netsquid.components import QuantumProcessor
from netsquid.components.component import Port
from netsquid.nodes import Node
from netsquid.nodes.network import Network
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
)

from squidasm.sim.stack.host import Host, HostComponent
from squidasm.sim.stack.qnos import Qnos, QnosComponent


class ProcessingNode(Node):
    def __init__(
        self,
        name: str,
        qdevice: QuantumProcessor,
        node_id: Optional[int] = None,
    ) -> None:
        super().__init__(name, ID=node_id)
        self.qmemory = qdevice

        qnos_comp = QnosComponent(self)
        self.add_subcomponent(qnos_comp, "qnos")

        host_comp = HostComponent(self)
        self.add_subcomponent(host_comp, "host")

        self.host_comp.ports["qnos_out"].connect(self.qnos_comp.ports["host_in"])
        self.host_comp.ports["qnos_in"].connect(self.qnos_comp.ports["host_out"])

        # Ports for communicating with other nodes
        self.add_ports(["qnos_peer_out", "qnos_peer_in"])
        self.add_ports(["host_peer_out", "host_peer_in"])

        self.qnos_comp.peer_out_port.forward_output(self.qnos_peer_out_port)
        self.qnos_peer_in_port.forward_input(self.qnos_comp.peer_in_port)
        self.host_comp.peer_out_port.forward_output(self.host_peer_out_port)
        self.host_peer_in_port.forward_input(self.host_comp.peer_in_port)

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.subcomponents["qnos"]

    @property
    def host_comp(self) -> HostComponent:
        return self.subcomponents["host"]

    @property
    def qdevice(self) -> QuantumProcessor:
        return self.qmemory

    @property
    def host_peer_in_port(self) -> Port:
        return self.ports["host_peer_in"]

    @property
    def host_peer_out_port(self) -> Port:
        return self.ports["host_peer_out"]

    @property
    def qnos_peer_in_port(self) -> Port:
        return self.ports["qnos_peer_in"]

    @property
    def qnos_peer_out_port(self) -> Port:
        return self.ports["qnos_peer_out"]


class NodeStack(Protocol):
    def __init__(
        self,
        name: str,
        node: Optional[ProcessingNode] = None,
        qdevice_type: Optional[str] = "generic",
        qdevice: Optional[QuantumProcessor] = None,
        node_id: Optional[int] = None,
        use_default_components: bool = True,
    ) -> None:
        super().__init__(name=f"{name}")
        if node:
            self._node = node
        else:
            assert qdevice is not None
            self._node = ProcessingNode(name, qdevice, node_id)

        self._host: Optional[Host]
        self._qnos: Optional[Qnos]

        if use_default_components:
            self._host = Host(self.host_comp, qdevice_type)
            self._qnos = Qnos(self.qnos_comp, qdevice_type)
        else:
            self._host = None
            self._qnos = None

    def assign_ll_protocol(self, prot: MagicLinkLayerProtocolWithSignaling) -> None:
        self.qnos.assign_ll_protocol(prot)

    @property
    def node(self) -> ProcessingNode:
        return self._node

    @property
    def host_comp(self) -> HostComponent:
        return self.node.host_comp

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.node.qnos_comp

    @property
    def qdevice(self) -> QuantumProcessor:
        return self.node.qdevice

    @property
    def host(self) -> Host:
        return self._host

    @host.setter
    def host(self, host: Host) -> None:
        self._host = host

    @property
    def qnos(self) -> Qnos:
        return self._qnos

    @qnos.setter
    def qnos(self, qnos: Qnos) -> None:
        self._qnos = qnos

    def connect_to(self, other: NodeStack) -> None:
        self.node.host_peer_out_port.connect(other.node.host_peer_in_port)
        self.node.host_peer_in_port.connect(other.node.host_peer_out_port)
        self.node.qnos_peer_out_port.connect(other.node.qnos_peer_in_port)
        self.node.qnos_peer_in_port.connect(other.node.qnos_peer_out_port)

    def start(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        super().start()
        self._host.start()
        self._qnos.start()

    def stop(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        self._qnos.stop()
        self._host.stop()
        super().stop()


class StackNetwork(Network):
    def __init__(
        self, stacks: Dict[str, NodeStack], links: List[MagicLinkLayerProtocol]
    ) -> None:
        self._stacks = stacks
        self._links = links

    @property
    def stacks(self) -> Dict[str, NodeStack]:
        return self._stacks

    @property
    def links(self) -> List[MagicLinkLayerProtocol]:
        return self._links

    @property
    def qdevices(self) -> Dict[str, QuantumProcessor]:
        return {name: stack.qdevice for name, stack in self._stacks.items()}
