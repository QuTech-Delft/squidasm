from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
)
from netqasm.sdk.compiling import NVSubroutineCompiler, SubroutineCompiler
from netqasm.sdk.epr_socket import EPRSocket
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.sim.stack.common import ComponentProtocol, PortListener
from squidasm.sim.stack.connection import QnosConnection
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext
from squidasm.sim.stack.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG


class HostComponent(Component):
    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_host")
        self.add_ports(["qnos_in", "qnos_out"])
        self.add_ports(["peer_in", "peer_out"])

    @property
    def qnos_in_port(self) -> Port:
        return self.ports["qnos_in"]

    @property
    def qnos_out_port(self) -> Port:
        return self.ports["qnos_out"]

    @property
    def peer_in_port(self) -> Port:
        return self.ports["peer_in"]

    @property
    def peer_out_port(self) -> Port:
        return self.ports["peer_out"]


class Host(ComponentProtocol):
    def __init__(self, comp: HostComponent, qdevice_type: Optional[str] = "nv") -> None:
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp

        self.add_listener(
            "qnos",
            PortListener(self._comp.ports["qnos_in"], SIGNAL_HAND_HOST_MSG),
        )
        self.add_listener(
            "peer",
            PortListener(self._comp.ports["peer_in"], SIGNAL_HOST_HOST_MSG),
        )

        if qdevice_type == "nv":
            self._compiler: Optional[Type[SubroutineCompiler]] = NVSubroutineCompiler
        elif qdevice_type == "generic":
            self._compiler: Optional[Type[SubroutineCompiler]] = None
        else:
            raise ValueError

        self._program: Optional[Program] = None
        self._num_pending: int = 0
        self._program_results: List[Dict[str, Any]] = []

    @property
    def compiler(self) -> Optional[Type[SubroutineCompiler]]:
        return self._compiler

    @compiler.setter
    def compiler(self, typ: Optional[Type[SubroutineCompiler]]) -> None:
        self._compiler = typ

    def send_qnos_msg(self, msg: bytes) -> None:
        self._comp.qnos_out_port.tx_output(msg)

    def receive_qnos_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("qnos", SIGNAL_HAND_HOST_MSG))

    def send_peer_msg(self, msg: str) -> None:
        self._comp.peer_out_port.tx_output(msg)

    def receive_peer_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("peer", SIGNAL_HOST_HOST_MSG))

    def run(self) -> Generator[EventExpression, None, None]:
        while self._num_pending > 0:
            self._logger.info(f"num pending: {self._num_pending}")
            self._num_pending -= 1

            assert self._program is not None
            prog_meta = self._program.meta
            self.send_qnos_msg(
                bytes(InitNewAppMessage(max_qubits=prog_meta.max_qubits))
            )
            app_id = yield from self.receive_qnos_msg()
            self._logger.debug(f"got app id from qnos: {app_id}")

            conn = QnosConnection(
                self,
                app_id,
                prog_meta.name,
                max_qubits=prog_meta.max_qubits,
                compiler=self._compiler,
            )

            epr_sockets: Dict[int, EPRSocket] = {}
            for i, remote_name in enumerate(prog_meta.epr_sockets):
                remote_id = None
                nodes = NetSquidContext.get_nodes()
                for id, name in nodes.items():
                    if name == remote_name:
                        remote_id = id
                assert remote_id is not None
                self.send_qnos_msg(bytes(OpenEPRSocketMessage(app_id, i, remote_id)))
                epr_sockets[remote_name] = EPRSocket(remote_name, i)
                epr_sockets[remote_name].conn = conn

            classical_sockets: Dict[int, ClassicalSocket] = {}
            for i, remote_name in enumerate(prog_meta.csockets):
                remote_id = None
                nodes = NetSquidContext.get_nodes()
                for id, name in nodes.items():
                    if name == remote_name:
                        remote_id = id
                assert remote_id is not None
                classical_sockets[remote_name] = ClassicalSocket(
                    self, prog_meta.name, remote_name
                )

            context = ProgramContext(
                netqasm_connection=conn,
                csockets=classical_sockets,
                epr_sockets=epr_sockets,
                app_id=app_id,
            )

            result = yield from self._program.run(context)
            self._program_results.append(result)
            self.send_qnos_msg(bytes(StopAppMessage(app_id)))

    def enqueue_program(self, program: Program, num_times: int = 1):
        self._program = program
        self._num_pending = num_times

    def get_results(self) -> List[Dict[str, Any]]:
        return self._program_results
