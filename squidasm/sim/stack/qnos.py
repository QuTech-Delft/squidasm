from __future__ import annotations

from typing import Dict, Optional, Tuple

from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.sim.stack.common import (
    AppMemory,
    NVPhysicalQuantumMemory,
    PhysicalQuantumMemory,
)
from squidasm.sim.stack.handler import Handler, HandlerComponent
from squidasm.sim.stack.netstack import Netstack, NetstackComponent
from squidasm.sim.stack.processor import (
    GenericProcessor,
    NVProcessor,
    Processor,
    ProcessorComponent,
)

# TODO: make this a parameter
NUM_QUBITS = 5


class QnosComponent(Component):
    def __init__(self, node: Node) -> None:
        super().__init__(name=f"{node.name}_qnos")
        self._node = node

        # Ports for communicating with Host
        self.add_ports(["host_out", "host_in"])

        # Ports for communicating with other nodes
        self.add_ports(["peer_out", "peer_in"])

        comp_handler = HandlerComponent(node)
        self.add_subcomponent(comp_handler, "handler")

        comp_processor = ProcessorComponent(node)
        self.add_subcomponent(comp_processor, "processor")

        comp_netstack = NetstackComponent(node)
        self.add_subcomponent(comp_netstack, "netstack")

        self.netstack_comp.ports["peer_out"].forward_output(self.peer_out_port)
        self.peer_in_port.forward_input(self.netstack_comp.ports["peer_in"])

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

    @property
    def peer_in_port(self) -> Port:
        return self.ports["peer_in"]

    @property
    def peer_out_port(self) -> Port:
        return self.ports["peer_out"]

    @property
    def node(self) -> Node:
        return self._node


class Qnos(Protocol):
    def __init__(self, comp: QnosComponent, qdevice_type: Optional[str] = "nv") -> None:
        super().__init__(name=f"{comp.name}_protocol")
        self._comp = comp

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

        self._app_memories: Dict[int, AppMemory] = {}

    # TODO: move this to a separate memory manager object
    def get_virt_qubit_for_phys_id(self, phys_id: int) -> Tuple[int, int]:
        # returns (app_id, virt_id)
        for app_id, app_mem in self._app_memories.items():
            virt_id = app_mem.virt_id_for(phys_id)
            if virt_id is not None:
                return app_id, virt_id
        raise RuntimeError(f"no virtual ID found for physical ID {phys_id}")

    def assign_ll_protocol(self, prot: MagicLinkLayerProtocolWithSignaling) -> None:
        self.netstack.assign_ll_protocol(prot)

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
