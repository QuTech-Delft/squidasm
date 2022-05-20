from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
)
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
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
    """NetSquid compmonent representing a Host.

    Subcomponent of a ProcessingNode.

    This is a static container for Host-related components and ports. Behavior
    of a Host is modeled in the `Host` class, which is a subclass of `Protocol`.
    """

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
    """NetSquid protocol representing a Host."""

    def __init__(self, comp: HostComponent, qdevice_type: Optional[str] = "nv") -> None:
        """Qnos protocol constructor.

        :param comp: NetSquid component representing the Host
        :param qdevice_type: hardware type of the QDevice of this node
        """
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
            self._compiler: Optional[
                Type[SubroutineTranspiler]
            ] = NVSubroutineTranspiler
        elif qdevice_type == "generic":
            self._compiler: Optional[Type[SubroutineTranspiler]] = None
        else:
            raise ValueError

        # Program that is currently being executed.
        self._program: Optional[Program] = None

        # Number of times the current program still needs to be run.
        self._num_pending: int = 0

        # Results of program runs so far.
        self._program_results: List[Dict[str, Any]] = []

    @property
    def compiler(self) -> Optional[Type[SubroutineTranspiler]]:
        return self._compiler

    @compiler.setter
    def compiler(self, typ: Optional[Type[SubroutineTranspiler]]) -> None:
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
        """Run this protocol. Automatically called by NetSquid during simulation."""

        # Run a single program as many times as requested.
        while self._num_pending > 0:
            self._logger.info(f"num pending: {self._num_pending}")
            self._num_pending -= 1

            assert self._program is not None
            prog_meta = self._program.meta

            # Register the new program (called 'application' by QNodeOS) with QNodeOS.
            self.send_qnos_msg(
                bytes(InitNewAppMessage(max_qubits=prog_meta.max_qubits))
            )
            app_id = yield from self.receive_qnos_msg()
            self._logger.debug(f"got app id from qnos: {app_id}")

            # Set up the Connection object to be used by the program SDK code.
            conn = QnosConnection(
                self,
                app_id,
                prog_meta.name,
                max_qubits=prog_meta.max_qubits,
                compiler=self._compiler,
            )

            # Create EPR sockets that can be used by the program SDK code.
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

            # Create classical sockets that can be used by the program SDK code.
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

            # Run the program by evaluating its run() method.
            result = yield from self._program.run(context)
            self._program_results.append(result)

            # Tell QNodeOS the program has finished.
            self.send_qnos_msg(bytes(StopAppMessage(app_id)))

    def enqueue_program(self, program: Program, num_times: int = 1):
        """Queue a program to be run the given number of times.

        NOTE: At the moment, only a single program can be queued at a time."""
        self._program = program
        self._num_pending = num_times

    def get_results(self) -> List[Dict[str, Any]]:
        return self._program_results
