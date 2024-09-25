from __future__ import annotations

from typing import Dict, List, Optional

from netsquid.components import QuantumProcessor
from netsquid.components.component import Port
from netsquid.nodes.network import Network
from netsquid.protocols import Protocol
from netsquid_driver.classical_socket_service import ClassicalSocket
from netsquid_magic.egp import EgpProtocol
from netsquid_magic.link_layer import MagicLinkLayerProtocol
from netsquid_netbuilder.network import QDeviceNode

from squidasm.sim.stack.host import Host, HostComponent
from squidasm.sim.stack.qnos import Qnos, QnosComponent


class StackNode(QDeviceNode):
    """NetSquid component representing a quantum network node containing a software
    stack consisting of Host, QNodeOS and QDevice.

    This component has two subcomponents: a QnosComponent and a HostComponent.

    Has communications ports between
     - the Host component on this node and the Host component on the peer node
     - the QNodeOS component on this node and the QNodeOS component on the peer node

    For now, it is assumed there is only a single other nodes in the network,
    which is "the" peer.

    This is a static container for components and ports.
    Behavior of the node is modeled in the `NodeStack` class, which is a subclass
    of `Protocol`.
    """

    def __init__(
        self,
        name: str,
        qdevice: QuantumProcessor,
        qdevice_type: str,
        node_id: Optional[int] = None,
    ) -> None:
        """ProcessingNode constructor. Typically created indirectly through
        constructing a `NodeStack`."""
        super().__init__(
            name, qdevice=qdevice, qdevice_type=qdevice_type, node_id=node_id
        )

        qnos_comp = QnosComponent(self)
        self.add_subcomponent(qnos_comp, "qnos")

        host_comp = HostComponent(self)
        self.add_subcomponent(host_comp, "host")

        self.host_comp.ports["qnos_out"].connect(self.qnos_comp.ports["host_in"])
        self.host_comp.ports["qnos_in"].connect(self.qnos_comp.ports["host_out"])

        # Ports for communicating with other nodes
        self.add_ports(["qnos_peer_out", "qnos_peer_in"])

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.subcomponents["qnos"]

    @property
    def host_comp(self) -> HostComponent:
        return self.subcomponents["host"]

    def qnos_peer_port(self, peer_id: int) -> Port:
        return self.ports[f"qnos_peer_{peer_id}"]

    def register_peer(self, peer_id: int):
        self.add_ports([f"qnos_peer_{peer_id}"])
        self.qnos_comp.register_peer(peer_id)
        self.qnos_comp.peer_out_port(peer_id).forward_output(
            self.qnos_peer_port(peer_id)
        )
        self.qnos_peer_port(peer_id).forward_input(self.qnos_comp.peer_in_port(peer_id))


class NodeStack(Protocol):
    """NetSquid protocol representing a node with a software stack.

    The software stack consists of a Host, QNodeOS and a QDevice.
    The Host and QNodeOS are each represented by separate subprotocols.
    The QDevice is handled/modeled as part of the QNodeOS protocol.
    """

    def __init__(
        self,
        name: str,
        node: Optional[StackNode] = None,
        qdevice_type: Optional[str] = "generic",
        qdevice: Optional[QuantumProcessor] = None,
        node_id: Optional[int] = None,
        use_default_components: bool = True,
    ) -> None:
        """NodeStack constructor.

        :param name: name of this node
        :param node: an existing ProcessingNode object containing the static
            components or None. If None, a ProcessingNode is automatically
            created.
        :param qdevice_type: hardware type of the QDevice, defaults to "generic"
        :param qdevice: NetSquid `QuantumProcessor` representing the QDevice,
            defaults to None. If None, a QuantumProcessor is created
            automatically.
        :param node_id: ID to use for the internal NetSquid node object
        :param use_default_components: whether to automatically create NetSquid
            components for the Host and QNodeOS, defaults to True. If False,
            this allows for manually creating and adding these components.
        """
        super().__init__(name=f"{name}")
        if node:
            self._node = node
        else:
            assert qdevice is not None
            self._node = StackNode(name, qdevice, node_id)

        self._host: Optional[Host] = None
        self._qnos: Optional[Qnos] = None

        # Create internal components.
        # If `use_default_components` is False, these components must be manually
        # created and added to this NodeStack.
        if use_default_components:
            self._host = Host(self.host_comp, qdevice_type)
            self._qnos = Qnos(self.qnos_comp, qdevice_type)

    def assign_egp(self, remote_node_id: int, egp: EgpProtocol) -> None:
        """Set the EGP protocol that this network stack uses to produce
        entangled pairs with a remote node.

        :param remote_node_id: The ID of the remote node.
        :param egp: The EGP protocol instance for generating EPR pairs with the remote node.
        """
        self.qnos.assign_egp(remote_node_id, egp)

    @property
    def node(self) -> StackNode:
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
    """A network of `NodeStack`s connected by links, which are
    `MagicLinkLayerProtocol`s."""

    def __init__(
        self,
        stacks: Dict[str, NodeStack],
        links: List[MagicLinkLayerProtocol],
        csockets: Dict[(str, str), ClassicalSocket],
    ) -> None:
        """StackNetwork constructor.

        :param stacks: dictionary of node name to `NodeStack` object representing
        that node
        :param links: list of link layer protocol objects. Each object internally
        contains the IDs of the two nodes that this link connects
        """
        self._stacks = stacks
        self._links = links
        self._csockets = csockets

    @property
    def stacks(self) -> Dict[str, NodeStack]:
        return self._stacks

    @property
    def links(self) -> List[MagicLinkLayerProtocol]:
        return self._links

    @property
    def csockets(self) -> Dict[(str, str), ClassicalSocket]:
        return self._csockets

    @property
    def qdevices(self) -> Dict[str, QuantumProcessor]:
        return {name: stack.qdevice for name, stack in self._stacks.items()}
