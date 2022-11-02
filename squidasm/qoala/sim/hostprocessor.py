from __future__ import annotations

import logging
from typing import Generator

from netqasm.lang.operand import Register
from netqasm.lang.parsing.text import NetQASMSyntaxError, parse_register

from pydynaa import EventExpression
from squidasm.qoala.lang import iqoala
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.process import IqoalaProcess


class HostProcessor:
    """Does not have state itself. Acts on and changes process objects."""

    def __init__(self, interface: HostInterface) -> None:
        self._interface = interface

        # TODO: name
        self._name = f"{interface.name}_HostProcessor"
        self._logger: logging.Logger = LogManager.get_stack_logger(  # type: ignore
            f"{self.__class__.__name__}({self._name})"
        )

    def initialize(self, process: IqoalaProcess) -> None:
        host_mem = process.prog_memory.host_mem
        inputs = process.prog_instance.inputs
        for name, value in inputs.values.items():
            host_mem.write(name, value)

    def assign(
        self, process: IqoalaProcess, instr_idx: int
    ) -> Generator[EventExpression, None, None]:
        csockets = process.csockets
        host_mem = process.prog_memory.host_mem
        shared_mem = process.prog_memory.shared_mem
        pid = process.prog_instance.pid
        program = process.prog_instance.program

        instr = program.instructions[instr_idx]

        self._logger.info(f"Interpreting LHR instruction {instr}")
        if isinstance(instr, iqoala.AssignCValueOp):
            value = instr.attributes[0]
            host_mem.write(instr.results[0], instr.attributes[0])
        elif isinstance(instr, iqoala.SendCMsgOp):
            csck_id = host_mem.read(instr.arguments[0])
            csck = csockets[csck_id]
            value = host_mem.read(instr.arguments[1])
            self._logger.info(f"sending msg {value}")
            csck.send_int(value)
        elif isinstance(instr, iqoala.ReceiveCMsgOp):
            csck_id = host_mem.read(instr.arguments[0])
            csck = csockets[csck_id]
            msg = yield from csck.recv_int()
            host_mem.write(instr.results[0], msg)
            self._logger.info(f"received msg {msg}")
        elif isinstance(instr, iqoala.AddCValueOp):
            arg0 = host_mem.read(instr.arguments[0])
            arg1 = host_mem.read(instr.arguments[1])
            host_mem.write(instr.results[0], arg0 + arg1)
        elif isinstance(instr, iqoala.MultiplyConstantCValueOp):
            arg0 = host_mem.read(instr.arguments[0])
            const = instr.attributes[0]
            assert isinstance(const, int)
            host_mem.write(instr.results[0], arg0 * const)
        elif isinstance(instr, iqoala.BitConditionalMultiplyConstantCValueOp):
            arg0 = host_mem.read(instr.arguments[0])
            cond = host_mem.read(instr.arguments[1])
            const = instr.attributes[0]
            assert isinstance(const, int)
            if cond == 1:
                host_mem.write(instr.results[0], arg0 * const)
            else:
                host_mem.write(instr.results[0], arg0)
        elif isinstance(instr, iqoala.RunSubroutineOp):
            arg_vec: iqoala.IqoalaVector = instr.arguments[0]
            args = arg_vec.values
            subrt_name = instr.attributes[0]
            assert isinstance(subrt_name, str)

            iqoala_subrt = process.subroutines[subrt_name]
            self._logger.info(f"executing subroutine {iqoala_subrt}")

            arg_values = {arg: host_mem.read(arg) for arg in args}

            self._logger.info(f"instantiating subroutine with values {arg_values}")
            iqoala_subrt.subroutine.instantiate(pid, arg_values)

            self._interface.send_qnos_msg(Message(subrt_name))
            yield from self._interface.receive_qnos_msg()
            # Qnos should have updated the shared memory with subroutine results.

            for key, mem_loc in iqoala_subrt.return_map.items():
                try:
                    reg: Register = parse_register(mem_loc.loc)
                    value = shared_mem.get_register(reg)
                    self._logger.debug(
                        f"writing shared memory value {value} from location "
                        f"{mem_loc} to variable {key}"
                    )
                    host_mem.write(key, value)
                except NetQASMSyntaxError:
                    pass
        elif isinstance(instr, iqoala.ReturnResultOp):
            value = instr.arguments[0]
            process.result.values[value] = host_mem.read(value)
