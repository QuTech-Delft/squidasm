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

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.qnos import Qnos
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.scheduler import Scheduler, SchedulerComponent


class ProcNodeComponent(Node):
    """NetSquid component representing a quantum network node containing a software
    stack consisting of Host, QNodeOS and QDevice.

    This component has three subcomponents:
        - a QnosComponent
        - a HostComponent
        - a SchedulerComponent

    Has communications ports between
     - the Host component on this node and the Host components on other nodes
     - the QNodeOS component on this node and the QNodeOS components on other nodes

    This is a static container for components and ports.
    Behavior of the node is modeled in the `ProcNode` class, which is a subclass
    of `Protocol`.

    This class is a subclass of the NetSquid `Node` class and can hence be used as
    a standard NetSquid node.
    """

    def __init__(
        self,
        name: str,
        qdevice: QuantumProcessor,
        global_env: GlobalEnvironment,
        node_id: Optional[int] = None,
    ) -> None:
        """ProcNodeComponent constructor. Typically created indirectly through
        constructing a `ProcNode`."""
        super().__init__(name, ID=node_id)
        self.qmemory = qdevice

        qnos_comp = QnosComponent(self, global_env)
        self.add_subcomponent(qnos_comp, "qnos")

        host_comp = HostComponent(self, global_env)
        self.add_subcomponent(host_comp, "host")

        comp_netstack = NetstackComponent(node, global_env)
        self.add_subcomponent(comp_netstack, "netstack")

        scheduler_comp = SchedulerComponent(self)
        self.add_subcomponent(scheduler_comp, "scheduler")

        self.host_comp.ports["qnos_out"].connect(self.qnos_comp.ports["host_in"])
        self.host_comp.ports["qnos_in"].connect(self.qnos_comp.ports["host_out"])

        # Ports for communicating with other nodes
        all_nodes = global_env.get_nodes().values()
        self._peers: List[str] = list(node.name for node in all_nodes)

        self._qnos_peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._qnos_peer_out_ports: Dict[str, str] = {}  # peer name -> port name
        self._host_peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._host_peer_out_ports: Dict[str, str] = {}  # peer name -> port name

        for peer in self._peers:
            qnos_port_in_name = f"qnos_peer_{peer}_in"
            qnos_port_out_name = f"qnos_peer_{peer}_out"
            self._qnos_peer_in_ports[peer] = qnos_port_in_name
            self._qnos_peer_out_ports[peer] = qnos_port_out_name

            host_port_in_name = f"host_peer_{peer}_in"
            host_port_out_name = f"host_peer_{peer}_out"
            self._host_peer_in_ports[peer] = host_port_in_name
            self._host_peer_out_ports[peer] = host_port_out_name

        self.add_ports(self._qnos_peer_in_ports.values())
        self.add_ports(self._qnos_peer_out_ports.values())
        self.add_ports(self._host_peer_in_ports.values())
        self.add_ports(self._host_peer_out_ports.values())

        for peer in self._peers:
            self.qnos_comp.peer_out_port(peer).forward_output(
                self.qnos_peer_out_port(peer)
            )
            self.qnos_peer_in_port(peer).forward_input(
                self.qnos_comp.peer_in_port(peer)
            )
            self.host_comp.peer_out_port(peer).forward_output(
                self.host_peer_out_port(peer)
            )
            self.host_peer_in_port(peer).forward_input(
                self.host_comp.peer_in_port(peer)
            )

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.subcomponents["qnos"]

    @property
    def host_comp(self) -> HostComponent:
        return self.subcomponents["host"]

    @property
    def scheduler_comp(self) -> SchedulerComponent:
        return self.subcomponents["scheduler"]

    @property
    def qdevice(self) -> QuantumProcessor:
        return self.qmemory

    def host_peer_in_port(self, name: str) -> Port:
        port_name = self._host_peer_in_ports[name]
        return self.ports[port_name]

    def host_peer_out_port(self, name: str) -> Port:
        port_name = self._host_peer_out_ports[name]
        return self.ports[port_name]

    def qnos_peer_in_port(self, name: str) -> Port:
        port_name = self._qnos_peer_in_ports[name]
        return self.ports[port_name]

    def qnos_peer_out_port(self, name: str) -> Port:
        port_name = self._qnos_peer_out_ports[name]
        return self.ports[port_name]


class ProcNode(Protocol):
    """NetSquid protocol representing a node with a software stack.

    The software stack consists of a Scheduler, Host, QNodeOS and a QDevice.
    The Host and QNodeOS are each represented by separate subprotocols.
    The QDevice is handled/modeled as part of the QNodeOS protocol.
    """

    def __init__(
        self,
        name: str,
        global_env: Optional[GlobalEnvironment] = None,
        node: Optional[ProcNodeComponent] = None,
        qdevice_type: Optional[str] = "generic",
        qdevice: Optional[QuantumProcessor] = None,
        node_id: Optional[int] = None,
        use_default_components: bool = True,
    ) -> None:
        """ProcNode constructor.

        :param name: name of this node
        :param node: an existing ProcNodeComponent object containing the static
            components or None. If None, a ProcNodeComponent is automatically
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
            self._node = ProcNodeComponent(name, qdevice, global_env, node_id)

        self._global_env = global_env
        self._local_env = LocalEnvironment(global_env, global_env.get_node_id(name))

        self._host: Optional[Host] = None
        self._qnos: Optional[Qnos] = None
        self._scheduler: Optional[Scheduler] = None

        # Create internal components.
        # If `use_default_components` is False, these components must be manually
        # created and added to this ProcNode.
        if use_default_components:
            self._host = Host(self.host_comp, self._local_env, qdevice_type)
            self._qnos = Qnos(self.qnos_comp, self._local_env, qdevice_type)
            self._scheduler = Scheduler(self.scheduler_comp, self._host, self._qnos)

    def install_environment(self) -> None:
        self._scheduler.install_schedule(self._local_env._local_schedule)
        for instance in self._local_env._programs:
            self._scheduler.init_new_program(instance)

    def assign_ll_protocol(
        self, remote_id: int, prot: MagicLinkLayerProtocolWithSignaling
    ) -> None:
        """Set the link layer protocol to use for entanglement generation.

        The same link layer protocol object is used by both nodes sharing a link in
        the network."""
        self.qnos.assign_ll_protocol(remote_id, prot)

    @property
    def node(self) -> ProcNodeComponent:
        return self._node

    @property
    def host_comp(self) -> HostComponent:
        return self.node.host_comp

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.node.qnos_comp

    @property
    def scheduler_comp(self) -> SchedulerComponent:
        return self.node.scheduler_comp

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

    @property
    def scheduler(self) -> Scheduler:
        return self._scheduler

    @scheduler.setter
    def scheduler(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def connect_to(self, other: ProcNode) -> None:
        """Create connections between ports of this ProcNode and those of
        another ProcNode."""
        here = self.node.name
        there = other.node.name
        self.node.host_peer_out_port(there).connect(other.node.host_peer_in_port(here))
        self.node.host_peer_in_port(there).connect(other.node.host_peer_out_port(here))
        self.node.qnos_peer_out_port(there).connect(other.node.qnos_peer_in_port(here))
        self.node.qnos_peer_in_port(there).connect(other.node.qnos_peer_out_port(here))

    def start(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        super().start()
        self._scheduler.start()
        self._host.start()
        self._qnos.start()

    def stop(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        self._qnos.stop()
        self._host.stop()
        self._scheduler.stop()
        super().stop()


class ProcNodeNetwork(Network):
    """A network of `ProcNode`s connected by links, which are
    `MagicLinkLayerProtocol`s."""

    def __init__(
        self, nodes: Dict[str, ProcNode], links: List[MagicLinkLayerProtocol]
    ) -> None:
        """ProcNodeNetwork constructor.

        :param nodes: dictionary of node name to `ProcNode` object representing
        that node
        :param links: list of link layer protocol objects. Each object internally
        contains the IDs of the two nodes that this link connects
        """
        self._nodes = nodes
        self._links = links

    @property
    def nodes(self) -> Dict[str, ProcNode]:
        return self._nodes

    @property
    def links(self) -> List[MagicLinkLayerProtocol]:
        return self._links

    @property
    def qdevices(self) -> Dict[str, QuantumProcessor]:
        return {name: node.qdevice for name, node in self._nodes.items()}
