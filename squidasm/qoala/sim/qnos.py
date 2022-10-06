from __future__ import annotations

from typing import Dict, Optional, Tuple

from netqasm.lang.subroutine import Subroutine
from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.nodes import Node
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.sim.common import NVPhysicalQuantumMemory, PhysicalQuantumMemory
from squidasm.qoala.sim.handler import Handler, HandlerComponent
from squidasm.qoala.sim.memory import ProgramMemory, QuantumMemory, SharedMemory
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.qnosprocessor import (
    GenericProcessor,
    NVProcessor,
    Processor,
    ProcessorComponent,
)


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
        # Each application has its own `ProgramMemory`, identified by the application ID.
        self._program_memories: Dict[int, ProgramMemory] = {}  # program ID -> memory

        # Subroutines contained in programs that are being run.
        # Nested mapping of program ID -> (subroutine name -> subroutine)
        self._program_subroutines: Dict[int, Dict[str, Subroutine]]

        self._processes: Dict[int, IqoalaProcess] = {}  # program ID -> process

    # TODO: move this to a separate memory manager object
    def get_virt_qubit_for_phys_id(self, phys_id: int) -> Tuple[int, int]:
        # returns (pid, virt_id)
        for pid, mem in self.quantum_memories:
            virt_id = mem.virt_id_for(phys_id)
            if virt_id is not None:
                return pid, virt_id
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
    def program_memories(self) -> Dict[int, ProgramMemory]:
        return self._program_memories

    @property
    def shared_memories(self) -> Dict[int, SharedMemory]:
        return {i: p.shared_mem for i, p in self._program_memories.items()}

    @property
    def quantum_memories(self) -> Dict[int, QuantumMemory]:
        return {i: p.quantum_mem for i, p in self._program_memories.items()}

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

    @property
    def program_memories(self) -> Dict[int, ProgramMemory]:
        """Get a dictionary of program IDs to their shared memories."""
        return self._qnos.program_memories

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        """Get the physical quantum memory object."""
        return self._qnos.physical_memory
