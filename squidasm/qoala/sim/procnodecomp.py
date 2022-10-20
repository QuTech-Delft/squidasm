from __future__ import annotations

from typing import Dict, List, Optional

from netsquid.components import QuantumProcessor
from netsquid.components.component import Port
from netsquid.nodes import Node

from squidasm.qoala.runtime.environment import GlobalEnvironment
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.netstack import NetstackComponent
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.scheduler import SchedulerComponent


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
        qprocessor: QuantumProcessor,
        global_env: GlobalEnvironment,
        node_id: Optional[int] = None,
    ) -> None:
        """ProcNodeComponent constructor. Typically created indirectly through
        constructing a `ProcNode`."""
        super().__init__(name, ID=node_id)
        self.qmemory = qprocessor

        qnos_comp = QnosComponent(self, global_env)
        self.add_subcomponent(qnos_comp, "qnos")

        host_comp = HostComponent(self, global_env)
        self.add_subcomponent(host_comp, "host")

        netstack_comp = NetstackComponent(self, global_env)
        self.add_subcomponent(netstack_comp, "netstack")

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
    def netstack_comp(self) -> NetstackComponent:
        return self.subcomponents["netstack"]

    @property
    def scheduler_comp(self) -> SchedulerComponent:
        return self.subcomponents["scheduler"]

    @property
    def qprocessor(self) -> QuantumProcessor:
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
