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
    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_handler")
        self._node = node
        self.add_ports(["proc_out", "proc_in"])
        self.add_ports(["host_out", "host_in"])

    @property
    def processor_in_port(self) -> Port:
        return self.ports["proc_in"]

    @property
    def processor_out_port(self) -> Port:
        return self.ports["proc_out"]

    @property
    def host_in_port(self) -> Port:
        return self.ports["host_in"]

    @property
    def host_out_port(self) -> Port:
        return self.ports["host_out"]

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
    def __init__(
        self, comp: HandlerComponent, qnos: Qnos, qdevice_type: Optional[str] = "nv"
    ) -> None:
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._qnos = qnos

        self.add_listener(
            "host",
            PortListener(self._comp.ports["host_in"], SIGNAL_HOST_HAND_MSG),
        )
        self.add_listener(
            "processor",
            PortListener(self._comp.ports["proc_in"], SIGNAL_PROC_HAND_MSG),
        )

        self._app_counter = 0
        self._applications: Dict[int, RunningApp] = {}

        self._clear_memory: bool = True

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
    def clear_memory(self) -> bool:
        return self._clear_memory

    @clear_memory.setter
    def clear_memory(self, value: bool) -> None:
        self._clear_memory = value

    @property
    def flavour(self) -> Optional[flavour.Flavour]:
        return self._flavour

    @flavour.setter
    def flavour(self, flavour: Optional[flavour.Flavour]) -> None:
        self._flavour = flavour

    def _send_host_msg(self, msg: Any) -> None:
        self._comp.host_out_port.tx_output(msg)

    def _receive_host_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("host", SIGNAL_HOST_HAND_MSG))

    def _send_processor_msg(self, msg: str) -> None:
        self._comp.processor_out_port.tx_output(msg)

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

    def open_epr_socket(self, app_id: int, socket_id: int, remote_id: int) -> None:
        self._logger.debug(f"Opening EPR socket ({socket_id}, {remote_id})")
        self.netstack.open_epr_socket(app_id, socket_id, remote_id)

    def add_subroutine(self, app_id: int, subroutine: Subroutine) -> None:
        self._applications[app_id].add_subroutine(subroutine)

    def _deserialize_subroutine(self, msg: SubroutineMessage) -> Subroutine:
        # return deser_subroutine(msg.subroutine, flavour=flavour.NVFlavour())
        return deser_subroutine(msg.subroutine, flavour=self._flavour)

    def clear_application(self, app_id: int) -> None:
        for virt_id, phys_id in self.app_memories[app_id].qubit_mapping.items():
            self.app_memories[app_id].unmap_virt_id(virt_id)
            if phys_id is not None:
                self.physical_memory.free(phys_id)
        self.app_memories.pop(app_id)

    def stop_application(self, app_id: int) -> None:
        self._logger.debug(f"stopping application with ID {app_id}")
        if self.clear_memory:
            self._logger.debug(f"clearing qubits for application with ID {app_id}")
            self.clear_application(app_id)
            self._applications.pop(app_id)
        else:
            self._logger.info(f"NOT clearing qubits for application with ID {app_id}")

    def assign_processor(
        self, app_id: int, subroutine: Subroutine
    ) -> Generator[EventExpression, None, AppMemory]:
        self._send_processor_msg(subroutine)
        result = yield from self._receive_processor_msg()
        assert result == "subroutine done"
        self._logger.debug(f"result: {result}")
        app_mem = self.app_memories[app_id]
        return app_mem

    def msg_from_host(self, msg: Message) -> None:
        if isinstance(msg, InitNewAppMessage):
            app_id = self.init_new_app(msg.max_qubits)
            self._send_host_msg(app_id)
        elif isinstance(msg, OpenEPRSocketMessage):
            self.open_epr_socket(msg.app_id, msg.epr_socket_id, msg.remote_node_id)
        elif isinstance(msg, SubroutineMessage):
            subroutine = self._deserialize_subroutine(msg)
            self.add_subroutine(subroutine.app_id, subroutine)
        elif isinstance(msg, StopAppMessage):
            self.stop_application(msg.app_id)

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            raw_host_msg = yield from self._receive_host_msg()
            self._logger.debug(f"received new msg from host: {raw_host_msg}")

            msg = deserialize_host_msg(raw_host_msg)
            self.msg_from_host(msg)

            app = self._next_app()
            if app is not None:
                # flush all pending subroutines for this app
                while True:
                    subrt = app.next_subroutine()
                    if subrt is None:
                        break
                    app_mem = yield from self.assign_processor(app.id, subrt)
                    self._send_host_msg(app_mem)
