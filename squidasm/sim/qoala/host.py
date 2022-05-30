from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
)
from netqasm.lang.operand import Register
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.run.qoala import lhr
from squidasm.sim.stack.common import ComponentProtocol, LogManager, PortListener
from squidasm.sim.stack.connection import QnosConnection
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext
from squidasm.sim.stack.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG


class LhrProcess:
    def __init__(self, host: Host, program: lhr.LhrProgram) -> None:
        self._host = host
        self._name = f"{host._comp.name}_Lhr"
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )
        self._program = program
        self._program_results: List[Dict[str, Any]] = []

    def setup(self) -> Generator[EventExpression, None, None]:
        program = self._program
        prog_meta = program.meta

        # Register the new program (called 'application' by QNodeOS) with QNodeOS.
        self._host.send_qnos_msg(
            bytes(InitNewAppMessage(max_qubits=prog_meta.max_qubits))
        )
        self._app_id = yield from self._host.receive_qnos_msg()
        self._logger.debug(f"got app id from qnos: {self._app_id}")

        # Set up the connection with QNodeOS.
        conn = QnosConnection(
            host=self._host,
            app_id=self._app_id,
            app_name=prog_meta.name,
            max_qubits=prog_meta.max_qubits,
            compiler=self._host._compiler,
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
            self._host.send_qnos_msg(
                bytes(OpenEPRSocketMessage(self._app_id, i, remote_id))
            )
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
                self._host, prog_meta.name, remote_name
            )

        self._context = ProgramContext(
            netqasm_connection=conn,
            csockets=classical_sockets,
            epr_sockets=epr_sockets,
            app_id=self._app_id,
        )

        self._memory: Dict[str, Any] = {}

    def run(self, num_times: int) -> Generator[EventExpression, None, None]:
        for _ in range(num_times):
            yield from self.setup()
            result = yield from self.execute_program()
            self._program_results.append(result)
            self._host.send_qnos_msg(bytes(StopAppMessage(self._app_id)))

    def run_with_context(
        self, context: ProgramContext, num_times: int
    ) -> Generator[EventExpression, None, None]:
        self._memory: Dict[str, Any] = {}
        self._context = context
        for _ in range(num_times):
            result = yield from self.execute_program()
            self._program_results.append(result)
            self._host.send_qnos_msg(bytes(StopAppMessage(context.app_id)))

    @property
    def context(self) -> ProgramContext:
        return self._context

    @property
    def memory(self) -> Dict[str, Any]:
        return self._memory

    @property
    def program(self) -> ProgramContext:
        return self._program

    def execute_program(self) -> Generator[EventExpression, None, Dict[str, Any]]:
        context = self._context
        memory = self._memory
        program = self._program

        csockets = list(context.csockets.values())
        csck = csockets[0] if len(csockets) > 0 else None
        conn = context.connection

        results: Dict[str, Any] = {}

        for instr in program.instructions:
            self._logger.info(f"Interpreting LHR instruction {instr}")
            if isinstance(instr, lhr.SendCMsgOp):
                value = memory[instr.arguments[0]]
                self._logger.info(f"sending msg {value}")
                csck.send(value)
            elif isinstance(instr, lhr.ReceiveCMsgOp):
                msg = yield from csck.recv()
                msg = int(msg)
                memory[instr.results[0]] = msg
                self._logger.info(f"received msg {msg}")
            elif isinstance(instr, lhr.AddCValueOp):
                arg0 = memory[instr.arguments[0]]
                arg1 = memory[instr.arguments[1]]
                memory[instr.results[0]] = arg0 + arg1
            elif isinstance(instr, lhr.MultiplyConstantCValueOp):
                arg0 = memory[instr.arguments[0]]
                arg1 = instr.arguments[1]
                memory[instr.results[0]] = arg0 * arg1
            elif isinstance(instr, lhr.BitConditionalMultiplyConstantCValueOp):
                arg0 = memory[instr.arguments[0]]
                arg1 = instr.arguments[1]
                cond = memory[instr.arguments[2]]
                if cond == 1:
                    memory[instr.results[0]] = arg0 * arg1
            elif isinstance(instr, lhr.AssignCValueOp):
                value = instr.attributes[0]
                # if isinstance(value, str) and value.startswith("RegFuture__"):
                #     reg_str = value[len("RegFuture__") :]
                memory[instr.results[0]] = instr.attributes[0]
            elif isinstance(instr, lhr.RunSubroutineOp):
                arg_vec: lhr.LhrVector = instr.arguments[0]
                args = arg_vec.values
                lhr_subrt: lhr.LhrSubroutine = instr.attributes[0]
                subrt = lhr_subrt.subroutine
                self._logger.info(f"executing subroutine {subrt}")

                arg_values = {arg: memory[arg] for arg in args}

                self._logger.warning(
                    f"instantiating subroutine with values {arg_values}"
                )
                subrt.instantiate(conn.app_id, arg_values)

                yield from conn.commit_subroutine(subrt)

                for key, mem_loc in lhr_subrt.return_map.items():
                    try:
                        reg: Register = parse_register(mem_loc.loc)
                        value = conn.shared_memory.get_register(reg)
                        self._logger.debug(
                            f"writing shared memory value {value} from location "
                            f"{mem_loc} to variable {key}"
                        )
                        memory[key] = value
                    except NetQASMSyntaxError:
                        pass
            elif isinstance(instr, lhr.ReturnResultOp):
                value = instr.arguments[0]
                results[value] = int(memory[value])

        return results


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

    def run_sdk_program(
        self, program: Program
    ) -> Generator[EventExpression, None, None]:
        prog_meta = program.meta

        # Register the new program (called 'application' by QNodeOS) with QNodeOS.
        self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=prog_meta.max_qubits)))
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
        result = yield from program.run(context)
        self._program_results.append(result)

        # Tell QNodeOS the program has finished.
        self.send_qnos_msg(bytes(StopAppMessage(app_id)))

    def run_lhr_sdk_program(
        self,
        program: lhr.LhrProgram,
    ) -> Generator[EventExpression, None, None]:
        prog_meta = program.meta

        # Register the new program (called 'application' by QNodeOS) with QNodeOS.
        self.send_qnos_msg(bytes(InitNewAppMessage(max_qubits=prog_meta.max_qubits)))
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

        lhr_program = program.compile(context)
        self._logger.warning(f"Runnign compiled SDK program:\n{lhr_program}")
        process = LhrProcess(self, lhr_program)
        yield from process.run_with_context(context, 1)
        self._program_results = process._program_results

    def run_lhr_program(
        self, program: lhr.LhrProgram, num_times: int
    ) -> Generator[EventExpression, None, None]:
        self._logger.warning(f"Creating LHR process for program:\n{program}")
        process = LhrProcess(self, program)
        result = yield from process.run(num_times)
        return result

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""

        # Run a single program as many times as requested.
        while self._num_pending > 0:
            self._logger.info(f"num pending: {self._num_pending}")
            self._num_pending -= 1

            assert self._program is not None

            if isinstance(self._program, lhr.LhrProgram):
                yield from self.run_lhr_program(self._program, 1)
            elif isinstance(self._program, lhr.SdkProgram):
                yield from self.run_lhr_sdk_program(self._program)
            else:
                self.run_sdk_program(self._program)

    def enqueue_program(self, program: Program, num_times: int = 1):
        """Queue a program to be run the given number of times.

        NOTE: At the moment, only a single program can be queued at a time."""
        self._program = program
        self._num_pending = num_times

    def get_results(self) -> List[Dict[str, Any]]:
        return self._program_results
