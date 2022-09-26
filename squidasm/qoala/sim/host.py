from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import StopAppMessage, SubroutineMessage
from netqasm.lang.operand import Register
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register
from netqasm.sdk.transpile import NVSubroutineTranspiler, SubroutineTranspiler
from netsquid.components.component import Component, Port
from netsquid.nodes import Node

from pydynaa import EventExpression
from squidasm.qoala.lang import iqoala
from squidasm.qoala.lang.iqoala import IqoalaProgram
from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.runtime.program import BatchResult, ProgramContext, ProgramInstance
from squidasm.qoala.sim.common import ComponentProtocol, PortListener
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.signals import SIGNAL_HAND_HOST_MSG, SIGNAL_HOST_HOST_MSG
from squidasm.qoala.sim.util import default_nv_unit_module


class IqoalaProcess:
    def __init__(
        self,
        host: Host,
        program_instance: ProgramInstance,
        program_memory: ProgramMemory,
        csockets: Dict[str, ClassicalSocket],
    ) -> None:
        self._host = host
        self._name = f"{host._comp.name}_Iqoala"
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )
        self._program_instance = program_instance
        self._results: Dict[str, Any] = {}

        self._csockets = csockets
        self._memory = program_memory

        self._instr_idx = 0

    @property
    def memory(self) -> Dict[str, Any]:
        return self._memory

    @property
    def csockets(self) -> Dict[str, ClassicalSocket]:
        return self._csockets

    @property
    def program_instance(self) -> ProgramInstance:
        return self._program_instance

    @property
    def instr_idx(self) -> int:
        return self._instr_idx

    @property
    def results(self) -> Dict[str, Any]:
        return self._results


class HostProcessor:
    def __init__(self, host: Host) -> None:
        self._host = host

        self._name = f"{host._comp.name}_HostProcessor"
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )

    def execute_process(
        self, process: IqoalaProcess, instr_idx: int
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csockets = process.csockets
        memory = process.memory.host_mem
        pid = process.program_instance.pid
        program = process.program_instance.program
        inputs = process.program_instance.inputs

        # TODO: support multiple csockets
        csck = csockets[0] if len(csockets) > 0 else None

        for name, value in inputs.items():
            memory[name] = value

        instr = program.instructions[instr_idx]

        self._logger.info(f"Interpreting LHR instruction {instr}")
        if isinstance(instr, iqoala.SendCMsgOp):
            value = memory[instr.arguments[0]]
            self._logger.info(f"sending msg {value}")
            csck.send(value)
        elif isinstance(instr, iqoala.ReceiveCMsgOp):
            msg = yield from csck.recv()
            msg = int(msg)
            memory[instr.results[0]] = msg
            self._logger.info(f"received msg {msg}")
        elif isinstance(instr, iqoala.AddCValueOp):
            arg0 = int(memory[instr.arguments[0]])
            arg1 = int(memory[instr.arguments[1]])
            memory[instr.results[0]] = arg0 + arg1
        elif isinstance(instr, iqoala.MultiplyConstantCValueOp):
            arg0 = memory[instr.arguments[0]]
            arg1 = int(instr.arguments[1])
            memory[instr.results[0]] = arg0 * arg1
        elif isinstance(instr, iqoala.BitConditionalMultiplyConstantCValueOp):
            arg0 = memory[instr.arguments[0]]
            arg1 = int(instr.arguments[1])
            cond = memory[instr.arguments[2]]
            if cond == 1:
                memory[instr.results[0]] = arg0 * arg1
            else:
                memory[instr.results[0]] = arg0
        elif isinstance(instr, iqoala.AssignCValueOp):
            value = instr.attributes[0]
            # if isinstance(value, str) and value.startswith("RegFuture__"):
            #     reg_str = value[len("RegFuture__") :]
            memory[instr.results[0]] = instr.attributes[0]
        elif isinstance(instr, iqoala.RunSubroutineOp):
            arg_vec: iqoala.IqoalaVector = instr.arguments[0]
            args = arg_vec.values
            iqoala_subrt: iqoala.IqoalaSubroutine = instr.attributes[0]
            subrt = iqoala_subrt.subroutine
            self._logger.info(f"executing subroutine {subrt}")

            arg_values = {arg: memory[arg] for arg in args}

            self._logger.info(f"instantiating subroutine with values {arg_values}")
            subrt.instantiate(pid, arg_values)

            self._host.send_qnos_msg(SubroutineMessage(subrt))
            yield from self._host.receive_qnos_msg()
            # Qnos should have updated the shared memory with subroutine results.

            for key, mem_loc in iqoala_subrt.return_map.items():
                try:
                    reg: Register = parse_register(mem_loc.loc)
                    value = memory.shared_mem.get_register(reg)
                    self._logger.debug(
                        f"writing shared memory value {value} from location "
                        f"{mem_loc} to variable {key}"
                    )
                    memory[key] = value
                except NetQASMSyntaxError:
                    pass
        elif isinstance(instr, iqoala.ReturnResultOp):
            value = instr.arguments[0]
            process.results[value] = int(memory[value])

    def execute_next_instr(
        self, process: IqoalaProcess
    ) -> Generator[EventExpression, None, None]:
        process.instr_idx += 1
        yield from self.execute_process(process, instr_idx=process.instr_idx)


class HostComponent(Component):
    """NetSquid component representing a Host.

    Subcomponent of a ProcNodeComponent.

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

        self._processor = HostProcessor(self)

    @property
    def processor(self) -> HostProcessor:
        return self._processor

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

    def run_iqoala_instr(
        self, process: IqoalaProcess, instr_idx: int
    ) -> Generator[EventExpression, None, None]:
        yield from process.run(instr_idx)

    def program_end(self, pid: int) -> BatchResult:
        self.send_qnos_msg(bytes(StopAppMessage(pid)))
        return self._processes[pid].get_results()

    def run(self) -> Generator[EventExpression, None, None]:
        """Run this protocol. Automatically called by NetSquid during simulation."""
        pass

    def run_process(self, pid: int) -> None:
        pass

    def get_results(self) -> List[Dict[str, Any]]:
        return self._program_results
