from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import StopAppMessage
from netqasm.lang.operand import Register
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang import lhr
from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.runtime.program import ProgramContext, ProgramInstance, SdkProgram
from squidasm.qoala.sim.common import (
    ComponentProtocol,
    LogManager,
    PortListener,
    ProgramResult,
)
from squidasm.qoala.sim.connection import QnosConnection
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG


class HostProgramContext(ProgramContext):
    def __init__(
        self,
        conn: QnosConnection,
        csockets: Dict[str, ClassicalSocket],
        app_id: int,
    ):
        self._conn = conn
        self._csockets = csockets
        self._app_id = app_id

    @property
    def conn(self) -> QnosConnection:
        return self._conn

    @property
    def csockets(self) -> Dict[str, ClassicalSocket]:
        return self._csockets

    @property
    def app_id(self) -> int:
        return self._app_id


class LhrProcess:
    def __init__(
        self, host: Host, program: ProgramInstance, context: HostProgramContext
    ) -> None:
        self._host = host
        self._name = f"{host._comp.name}_Lhr"
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )
        self._program = program
        self._program_results: List[Dict[str, Any]] = []

        self._context = context

        self._memory: Dict[str, Any] = {}

    def run(self, instr_idx: int) -> Generator[EventExpression, None, None]:
        # TODO multiple runs
        run_idx = 0
        assert len(self._program_results) in [run_idx, run_idx + 1]
        if len(self._program_results) == run_idx:
            self._program_results.append({})
        yield from self.execute_program(run_idx, instr_idx)

    @property
    def context(self) -> HostProgramContext:
        return self._context

    @property
    def memory(self) -> Dict[str, Any]:
        return self._memory

    @property
    def program(self) -> ProgramInstance:
        return self._program

    def get_results(self) -> ProgramResult:
        return ProgramResult(self._program_results)

    def execute_program(
        self, run_idx: int, instr_idx: int
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        context = self._context
        memory = self._memory
        program = self._program.program
        # TODO: result index !
        results = self._program_results[run_idx]

        csockets = list(self._context.csockets.values())
        csck = csockets[0] if len(csockets) > 0 else None
        conn = context.conn

        for name, value in self._program.inputs.items():
            memory[name] = value

        instr = program.instructions[instr_idx]

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
            arg0 = int(memory[instr.arguments[0]])
            arg1 = int(memory[instr.arguments[1]])
            memory[instr.results[0]] = arg0 + arg1
        elif isinstance(instr, lhr.MultiplyConstantCValueOp):
            arg0 = memory[instr.arguments[0]]
            arg1 = int(instr.arguments[1])
            memory[instr.results[0]] = arg0 * arg1
        elif isinstance(instr, lhr.BitConditionalMultiplyConstantCValueOp):
            arg0 = memory[instr.arguments[0]]
            arg1 = int(instr.arguments[1])
            cond = memory[instr.arguments[2]]
            if cond == 1:
                memory[instr.results[0]] = arg0 * arg1
            else:
                memory[instr.results[0]] = arg0
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

            self._logger.info(f"instantiating subroutine with values {arg_values}")
            subrt.instantiate(context.app_id, arg_values)

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


class HostComponent(Component):
    """NetSquid component representing a Host.

    Subcomponent of a ProcessingNode.

    This is a static container for Host-related components and ports. Behavior
    of a Host is modeled in the `Host` class, which is a subclass of `Protocol`.
    """

    def __init__(self, node: Node, global_env: GlobalEnvironment) -> None:
        super().__init__(f"{node.name}_host")

        self._peer_in_ports: Dict[str, str] = {}  # peer name -> port name
        self._peer_out_ports: Dict[str, str] = {}  # peer name -> port name

        for node in global_env.get_nodes().values():
            port_in_name = f"peer_{node.name}_in"
            port_out_name = f"peer_{node.name}_out"
            self._peer_in_ports[node.name] = port_in_name
            self._peer_out_ports[node.name] = port_out_name

        self.add_ports(self._peer_in_ports.values())
        self.add_ports(self._peer_out_ports.values())

        self.add_ports(["qnos_in", "qnos_out"])

    @property
    def qnos_in_port(self) -> Port:
        return self.ports["qnos_in"]

    @property
    def qnos_out_port(self) -> Port:
        return self.ports["qnos_out"]

    def peer_in_port(self, name: str) -> Port:
        port_name = self._peer_in_ports[name]
        return self.ports[port_name]

    def peer_out_port(self, name: str) -> Port:
        port_name = self._peer_out_ports[name]
        return self.ports[port_name]


class Host(ComponentProtocol):
    """NetSquid protocol representing a Host."""

    def __init__(
        self,
        comp: HostComponent,
        local_env: LocalEnvironment,
        qdevice_type: Optional[str] = "nv",
    ) -> None:
        """Host protocol constructor.

        :param comp: NetSquid component representing the Host
        :param qdevice_type: hardware type of the QDevice of this node
        """
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp

        self._local_env = local_env
        all_nodes = self._local_env.get_global_env().get_nodes().values()
        self._peers: List[str] = list(node.name for node in all_nodes)

        self.add_listener(
            "qnos",
            PortListener(self._comp.ports["qnos_in"], SIGNAL_HAND_HOST_MSG),
        )
        for peer in self._peers:
            self.add_listener(
                f"peer_{peer}",
                PortListener(
                    self._comp.peer_in_port(peer), f"{SIGNAL_HOST_HOST_MSG}_{peer}"
                ),
            )

        if qdevice_type == "nv":
            self._compiler: Optional[
                Type[SubroutineTranspiler]
            ] = NVSubroutineTranspiler
        elif qdevice_type == "generic":
            self._compiler: Optional[Type[SubroutineTranspiler]] = None
        else:
            raise ValueError

        # Programs that need to be executed.
        self._programs: Dict[int, ProgramInstance] = {}

        self._processes: Dict[int, LhrProcess] = {}

        self._connections: Dict[int, QnosConnection] = {}

        self._csockets: Dict[int, Dict[str, ClassicalSocket]] = {}

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

    @property
    def local_env(self) -> LocalEnvironment:
        return self._local_env

    def send_qnos_msg(self, msg: bytes) -> None:
        self._comp.qnos_out_port.tx_output(msg)

    def receive_qnos_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("qnos", SIGNAL_HAND_HOST_MSG))

    def send_peer_msg(self, peer: str, msg: str) -> None:
        self._comp.peer_out_port(peer).tx_output(msg)

    def receive_peer_msg(self, peer: str) -> Generator[EventExpression, None, str]:
        return (
            yield from self._receive_msg(
                f"peer_{peer}", f"{SIGNAL_HOST_HOST_MSG}_{peer}"
            )
        )

    def run_lhr_instr(
        self, app_id: int, instr_idx: int
    ) -> Generator[EventExpression, None, None]:
        process = self._processes[app_id]
        yield from process.run(instr_idx)

    def program_end(self, app_id: int) -> ProgramResult:
        self.send_qnos_msg(bytes(StopAppMessage(app_id)))
        return self._processes[app_id].get_results()

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""

        pass

    def init_new_program(self, program: ProgramInstance, program_id: int) -> None:
        app_id = program_id
        self._programs[app_id] = program

        conn = QnosConnection(
            host=self,
            app_id=app_id,
            app_name=program.program.meta.name,
            max_qubits=program.program.meta.max_qubits,
            compiler=self._compiler,
        )
        self._connections[app_id] = conn

        self._csockets[app_id] = {}

        context = HostProgramContext(
            conn=self._connections[app_id],
            csockets=self._csockets[app_id],
            app_id=app_id,
        )
        process = LhrProcess(self, program, context)
        self._processes[app_id] = process

    def open_csocket(self, app_id: int, remote_name: str) -> None:
        assert app_id in self._csockets
        self._csockets[app_id][remote_name] = ClassicalSocket(self, remote_name)

    def get_results(self) -> List[Dict[str, Any]]:
        return self._program_results
