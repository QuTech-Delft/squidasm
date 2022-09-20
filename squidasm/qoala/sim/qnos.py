from __future__ import annotations

from typing import Dict, Optional, Tuple

from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.common import (
    AppMemory,
    NVPhysicalQuantumMemory,
    PhysicalQuantumMemory,
)
from squidasm.qoala.sim.handler import Handler, HandlerComponent
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.processor import (
    GenericProcessor,
    NVProcessor,
    Processor,
    ProcessorComponent,
)


class QnosComponent(Component):
    """NetSquid component representing a QNodeOS instance.

    Subcomponent of a ProcNodeComponent.

    This is a static container for QNodeOS-related components and ports.
    Behavior of a QNodeOS instance is modeled in the `Qnos` class,
    which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node, global_env: GlobalEnvironment) -> None:
        super().__init__(name=f"{node.name}_qnos")
        self._node = node

        # Ports for communicating with Host
        self.add_ports(["host_out", "host_in"])

        self._peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._peer_out_ports: Dict[str, str] = {}  # peer name -> port name

        all_nodes = global_env.get_nodes().values()
        self._peers = list(node.name for node in all_nodes)

        for peer in self._peers:
            port_in_name = f"peer_{peer}_in"
            port_out_name = f"peer_{peer}_out"
            self._peer_in_ports[peer] = port_in_name
            self._peer_out_ports[peer] = port_out_name

        self.add_ports(self._peer_in_ports.values())
        self.add_ports(self._peer_out_ports.values())

        comp_handler = HandlerComponent(node)
        self.add_subcomponent(comp_handler, "handler")

        comp_processor = ProcessorComponent(node)
        self.add_subcomponent(comp_processor, "processor")

        comp_netstack = NetstackComponent(node, global_env)
        self.add_subcomponent(comp_netstack, "netstack")

        for peer in self._peer_in_ports.keys():
            self.netstack_comp.peer_out_port(peer).forward_output(
                self.peer_out_port(peer)
            )
        for peer in self._peer_out_ports.keys():
            self.peer_in_port(peer).forward_input(self.netstack_comp.peer_in_port(peer))

        self.handler_comp.ports["host_out"].forward_output(self.host_out_port)
        self.host_in_port.forward_input(self.handler_comp.ports["host_in"])

        self.handler_comp.processor_out_port.connect(
            self.processor_comp.handler_in_port
        )
        self.handler_comp.processor_in_port.connect(
            self.processor_comp.handler_out_port
        )

        self.processor_comp.netstack_out_port.connect(
            self.netstack_comp.processor_in_port
        )
        self.processor_comp.netstack_in_port.connect(
            self.netstack_comp.processor_out_port
        )

    @property
    def handler_comp(self) -> HandlerComponent:
        return self.subcomponents["handler"]

    @property
    def processor_comp(self) -> ProcessorComponent:
        return self.subcomponents["processor"]

    @property
    def netstack_comp(self) -> NetstackComponent:
        return self.subcomponents["netstack"]

    @property
    def qdevice(self) -> QuantumProcessor:
        return self.node.qmemory

    @property
    def host_in_port(self) -> Port:
        return self.ports["host_in"]

    @property
    def host_out_port(self) -> Port:
        return self.ports["host_out"]

    def peer_in_port(self, name: str) -> Port:
        port_name = self._peer_in_ports[name]
        return self.ports[port_name]

    def peer_out_port(self, name: str) -> Port:
        port_name = self._peer_out_ports[name]
        return self.ports[port_name]

    @property
    def node(self) -> Node:
        return self._node


class Qnos(Protocol):
    """NetSquid protocol representing a QNodeOS instance."""

    def __init__(
        self,
        comp: QnosComponent,
        local_env: LocalEnvironment,
        qdevice_type: Optional[str] = "nv",
    ) -> None:
        """Qnos protocol constructor.

        :param comp: NetSquid component representing the QNodeOS instance
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol")
        self._comp = comp

        self._local_env = local_env

        # Create internal protocols.
        self.handler = Handler(comp.handler_comp, self, qdevice_type)
        self.netstack = Netstack(comp.netstack_comp, self)
        if qdevice_type == "generic":
            self.processor = GenericProcessor(comp.processor_comp, self)
            self._physical_memory = PhysicalQuantumMemory(comp.qdevice.num_positions)
        elif qdevice_type == "nv":
            self.processor = NVProcessor(comp.processor_comp, self)
            self._physical_memory = NVPhysicalQuantumMemory(comp.qdevice.num_positions)
        else:
            raise ValueError

        # Classical memories that are shared (virtually) with the Host.
        # Each application has its own `AppMemory`, identified by the application ID.
        self._app_memories: Dict[int, AppMemory] = {}  # app ID -> app memory

    # TODO: move this to a separate memory manager object
    def get_virt_qubit_for_phys_id(self, phys_id: int) -> Tuple[int, int]:
        # returns (app_id, virt_id)
        for app_id, app_mem in self._app_memories.items():
            virt_id = app_mem.virt_id_for(phys_id)
            if virt_id is not None:
                return app_id, virt_id
        raise RuntimeError(f"no virtual ID found for physical ID {phys_id}")

    def assign_ll_protocol(
        self, remote_id: int, prot: MagicLinkLayerProtocolWithSignaling
    ) -> None:
        self.netstack.assign_ll_protocol(remote_id, prot)

    @property
    def handler(self) -> Handler:
        return self._handler

    @handler.setter
    def handler(self, handler: Handler) -> None:
        self._handler = handler

    @property
    def processor(self) -> Processor:
        return self._processor

    @processor.setter
    def processor(self, processor: Processor) -> None:
        self._processor = processor

    @property
    def netstack(self) -> Netstack:
        return self._netstack

    @netstack.setter
    def netstack(self, netstack: Netstack) -> None:
        self._netstack = netstack

    @property
    def app_memories(self) -> Dict[int, AppMemory]:
        return self._app_memories

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        return self._physical_memory

    def start(self) -> None:
        assert self._handler is not None
        assert self._processor is not None
        assert self._netstack is not None
        super().start()
        self._handler.start()
        self._processor.start()
        self._netstack.start()

    def stop(self) -> None:
        self._netstack.stop()
        self._processor.stop()
        self._handler.stop()
        super().stop()
