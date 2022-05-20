from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

from netqasm.backend.messages import (
    InitNewAppMessage,
    Message,
    OpenEPRSocketMessage,
    StopAppMessage,
    SubroutineMessage,
    deserialize_host_msg,
)
from netqasm.lang.instr import flavour
from netqasm.lang.parsing import deserialize as deser_subroutine
from netqasm.lang.subroutine import Subroutine
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.sim.stack.common import (
    AppMemory,
    ComponentProtocol,
    PhysicalQuantumMemory,
    PortListener,
)
from squidasm.sim.stack.netstack import Netstack, NetstackComponent
from squidasm.sim.stack.signals import SIGNAL_HOST_HAND_MSG, SIGNAL_PROC_HAND_MSG

if TYPE_CHECKING:
    from squidasm.sim.stack.processor import ProcessorComponent
    from squidasm.sim.stack.qnos import Qnos, QnosComponent


class HandlerComponent(Component):
    """NetSquid component representing a QNodeOS handler.

    Subcomponent of a QnosComponent.

    The "QnodeOS handler" represents the combination of the following components
    within QNodeOS:
     - interface with the Host
     - scheduler

    Has communications ports with
     - the processor component of this QNodeOS
     - the Host component on this node

    This is a static container for handler-related components and ports.
    Behavior of a QNodeOS handler is modeled in the `Handler` class,
    which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_handler")
        self._node = node
        self.add_ports(["proc"])
        self.add_ports(["host"])

    @property
    def processor_port(self) -> Port:
        return self.ports["proc"]

    @property
    def host_port(self) -> Port:
        return self.ports["host"]

    @property
    def node(self) -> Node:
        return self._node

    @property
    def processor_comp(self) -> ProcessorComponent:
        return self.supercomponent.processor

    @property
    def netstack_comp(self) -> NetstackComponent:
        return self.supercomponent.netstack

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.supercomponent


class RunningApp:
    def __init__(self, app_id: int) -> None:
        self._id = app_id
        self._pending_subroutines: List[Subroutine] = []

    def add_subroutine(self, subroutine: Subroutine) -> None:
        self._pending_subroutines.append(subroutine)

    def next_subroutine(self) -> Optional[Subroutine]:
        if len(self._pending_subroutines) > 0:
            return self._pending_subroutines.pop()
        return None

    @property
    def id(self) -> int:
        return self._id


class Handler(ComponentProtocol):
    """NetSquid protocol representing a QNodeOS handler."""

    def __init__(
        self, comp: HandlerComponent, qnos: Qnos, qdevice_type: Optional[str] = "nv"
    ) -> None:
        """Processor handler constructor. Typically created indirectly through
        constructing a `Qnos` instance.

        :param comp: NetSquid component representing the handler
        :param qnos: `Qnos` protocol that owns this protocol
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._qnos = qnos

        self.add_listener(
            "host",
            PortListener(self._comp.ports["host"], SIGNAL_HOST_HAND_MSG),
        )
        self.add_listener(
            "processor",
            PortListener(self._comp.ports["proc"], SIGNAL_PROC_HAND_MSG),
        )

        # Number of applications that were handled so far. Used as a unique ID for
        # the next application.
        self._app_counter = 0

        # Currently active (running or waiting) applications.
        self._applications: Dict[int, RunningApp] = {}

        # Whether the quantum memory for applications should be reset when the
        # application finishes.
        self._should_clear_memory: bool = True

        # Set the expected flavour such that Host messages are deserialized correctly.
        if qdevice_type == "nv":
            self._flavour: Optional[flavour.Flavour] = flavour.NVFlavour()
        elif qdevice_type == "generic":
            self._flavour: Optional[flavour.Flavour] = flavour.VanillaFlavour()
        else:
            raise ValueError

    @property
    def app_memories(self) -> Dict[int, AppMemory]:
        return self._qnos.app_memories

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        return self._qnos.physical_memory

    @property
    def should_clear_memory(self) -> bool:
        return self._should_clear_memory

    @should_clear_memory.setter
    def should_clear_memory(self, value: bool) -> None:
        self._should_clear_memory = value

    @property
    def flavour(self) -> Optional[flavour.Flavour]:
        return self._flavour

    @flavour.setter
    def flavour(self, flavour: Optional[flavour.Flavour]) -> None:
        self._flavour = flavour

    def _send_host_msg(self, msg: Any) -> None:
        self._comp.host_port.tx_output(msg)

    def _receive_host_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("host", SIGNAL_HOST_HAND_MSG))

    def _send_processor_msg(self, msg: str) -> None:
        self._comp.processor_port.tx_output(msg)

    def _receive_processor_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("processor", SIGNAL_PROC_HAND_MSG))

    @property
    def qnos(self) -> Qnos:
        return self._qnos

    @property
    def netstack(self) -> Netstack:
        return self.qnos.netstack

    def _next_app(self) -> Optional[RunningApp]:
        for app in self._applications.values():
            return app
        return None

    def init_new_app(self, max_qubits: int) -> int:
        app_id = self._app_counter
        self._app_counter += 1
        self.app_memories[app_id] = AppMemory(app_id, self.physical_memory.qubit_count)
        self._applications[app_id] = RunningApp(app_id)
        self._logger.debug(f"registered app with ID {app_id}")
        return app_id

    def open_epr_socket(
        self, app_id: int, socket_id: int, remote_id: int, min_fidelity: int = 0
    ) -> None:
        self._logger.debug(f"Opening EPR socket ({socket_id}, {remote_id})")
        self.netstack.open_epr_socket(app_id, socket_id, remote_id, min_fidelity)

    def add_subroutine(self, app_id: int, subroutine: Subroutine) -> None:
        self._applications[app_id].add_subroutine(subroutine)

    def _deserialize_subroutine(self, msg: SubroutineMessage) -> Subroutine:
        # return deser_subroutine(msg.subroutine, flavour=flavour.NVFlavour())
        return deser_subroutine(msg.subroutine, flavour=self._flavour)

    def clear_application(self, app_id: int, remove_app: bool = True) -> None:
        for virt_id, phys_id in self.app_memories[app_id].qubit_mapping.items():
            self.app_memories[app_id].unmap_virt_id(virt_id)
            if phys_id is not None:
                self.physical_memory.free(phys_id)
                # TODO
                self.qnos.processor.qdevice.mem_positions[phys_id].in_use = False
        # TODO comment
        if remove_app:
            self.app_memories.pop(app_id)

    def stop_application(self, app_id: int) -> None:
        self._logger.debug(f"stopping application with ID {app_id}")
        if self.should_clear_memory:
            self._logger.debug(f"clearing qubits for application with ID {app_id}")
            self.clear_application(app_id)
            self._applications.pop(app_id)
        else:
            self._logger.info(f"NOT clearing qubits for application with ID {app_id}")

    def assign_processor(
        self, app_id: int, subroutine: Subroutine
    ) -> Generator[EventExpression, None, Optional[AppMemory]]:
        """Tell the processor to execute a subroutine and wait for it to finish.

        :param app_id: ID of the application this subroutine is for
        :param subroutine: the subroutine to execute
        """
        self._send_processor_msg(subroutine)
        result = yield from self._receive_processor_msg()
        if result == "subroutine done":
            self._logger.debug(f"result: {result}")
            app_mem = self.app_memories[app_id]
            return app_mem
        else:
            # TODO
            assert result == "timeout"
            self.clear_application(app_id, remove_app=False)
            return None  # error

    def msg_from_host(self, msg: Message) -> None:
        """Handle a deserialized message from the Host."""
        if isinstance(msg, InitNewAppMessage):
            app_id = self.init_new_app(msg.max_qubits)
            self._send_host_msg(app_id)
        elif isinstance(msg, OpenEPRSocketMessage):
            self.open_epr_socket(
                msg.app_id, msg.epr_socket_id, msg.remote_node_id, msg.min_fidelity
            )
        elif isinstance(msg, SubroutineMessage):
            subroutine = self._deserialize_subroutine(msg)
            self.add_subroutine(subroutine.app_id, subroutine)
        elif isinstance(msg, StopAppMessage):
            self.stop_application(msg.app_id)

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""

        # Loop forever acting on messages from the Host.
        while True:
            # Wait for a new message from the Host.
            raw_host_msg = yield from self._receive_host_msg()
            self._logger.debug(f"received new msg from host: {raw_host_msg}")
            msg = deserialize_host_msg(raw_host_msg)

            # Handle the message. This updates the handler's state and may e.g.
            # add a pending subroutine for an application.
            self.msg_from_host(msg)

            # Get the next application that needs work.
            app = self._next_app()
            if app is not None:
                # Flush all pending subroutines for this app.
                while True:
                    subrt = app.next_subroutine()
                    if subrt is None:
                        break
                    app_mem = yield from self.assign_processor(app.id, subrt)
                    # TODO
                    if app_mem is not None:  # success
                        self._send_host_msg(app_mem)
                    else:
                        self._send_host_msg("abort")
