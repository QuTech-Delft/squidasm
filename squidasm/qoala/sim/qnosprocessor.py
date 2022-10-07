from __future__ import annotations

import logging
from typing import Generator, Optional, Union

import netsquid as ns
from netqasm.lang.instr import NetQASMInstruction, core, nv, vanilla
from netqasm.lang.operand import Register
from netsquid.components.instructions import (
    INSTR_CNOT,
    INSTR_CXDIR,
    INSTR_CYDIR,
    INSTR_CZ,
    INSTR_H,
    INSTR_INIT,
    INSTR_MEASURE,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_X,
    INSTR_Y,
    INSTR_Z,
)
from netsquid.components.instructions import Instruction as NsInstr
from netsquid.components.qprogram import QuantumProgram
from netsquid.qubits import qubitapi

from pydynaa import EventExpression
from squidasm.qoala.sim.common import (
    AllocError,
    NetstackBreakpointCreateRequest,
    NetstackBreakpointReceiveRequest,
    NetstackCreateRequest,
    NetstackReceiveRequest,
)
from squidasm.qoala.sim.constants import PI, PI_OVER_2
from squidasm.qoala.sim.globals import GlobalSimData
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice
from squidasm.qoala.sim.qnosinterface import QnosInterface
from squidasm.qoala.sim.signals import SIGNAL_MEMORY_FREED


class QnosProcessor:
    """Does not have state itself."""

    def __init__(self, interface: QnosInterface) -> None:
        self._interface = interface

        # TODO: rewrite
        self._node_name = interface._comp.node.name

        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._node_name})"
        )

        # memory of current program, only not-None when processor is active
        self._current_prog_mem: Optional[ProgramMemory] = None

    def _prog_mem(self) -> ProgramMemory:
        # May only be called when processor is active
        assert self._current_prog_mem is not None
        return self._current_prog_mem

    @property
    def qdevice(self) -> QDevice:
        return self._interface.qdevice

    def assign(
        self, process: IqoalaProcess, subrt_name: str, instr_idx: int
    ) -> Generator[EventExpression, None, None]:
        subroutine = process.subroutines[subrt_name]
        pid = process.prog_instance.pid

        self._current_prog_mem = process.prog_memory
        prog_mem = self._prog_mem()

        instr = subroutine.instructions[prog_mem.prog_counter]
        self._logger.debug(
            f"{ns.sim_time()} interpreting instruction {instr} at line {prog_mem.prog_counter}"
        )

        if (
            isinstance(instr, core.JmpInstruction)
            or isinstance(instr, core.BranchUnaryInstruction)
            or isinstance(instr, core.BranchBinaryInstruction)
        ):
            self._interpret_branch_instr(pid, instr)
        else:
            generator = self._interpret_instruction(pid, instr)
            if generator:
                yield from generator

        self._current_prog_mem = None

    def _interpret_instruction(
        self, pid: int, instr: NetQASMInstruction
    ) -> Optional[Generator[EventExpression, None, None]]:
        if isinstance(instr, core.SetInstruction):
            return self._interpret_set(pid, instr)
        elif isinstance(instr, core.QAllocInstruction):
            return self._interpret_qalloc(pid, instr)
        elif isinstance(instr, core.QFreeInstruction):
            return self._interpret_qfree(pid, instr)
        elif isinstance(instr, core.StoreInstruction):
            return self._interpret_store(pid, instr)
        elif isinstance(instr, core.LoadInstruction):
            return self._interpret_load(pid, instr)
        elif isinstance(instr, core.LeaInstruction):
            return self._interpret_lea(pid, instr)
        elif isinstance(instr, core.UndefInstruction):
            return self._interpret_undef(pid, instr)
        elif isinstance(instr, core.ArrayInstruction):
            return self._interpret_array(pid, instr)
        elif isinstance(instr, core.InitInstruction):
            return self._interpret_init(pid, instr)
        elif isinstance(instr, core.MeasInstruction):
            return self._interpret_meas(pid, instr)
        elif isinstance(instr, core.CreateEPRInstruction):
            return self._interpret_create_epr(pid, instr)
        elif isinstance(instr, core.RecvEPRInstruction):
            return self._interpret_recv_epr(pid, instr)
        elif isinstance(instr, core.WaitAllInstruction):
            return self._interpret_wait_all(pid, instr)
        elif isinstance(instr, core.RetRegInstruction):
            pass
        elif isinstance(instr, core.RetArrInstruction):
            pass
        elif isinstance(instr, core.SingleQubitInstruction):
            return self._interpret_single_qubit_instr(pid, instr)
        elif isinstance(instr, core.TwoQubitInstruction):
            return self._interpret_two_qubit_instr(pid, instr)
        elif isinstance(instr, core.RotationInstruction):
            return self._interpret_single_rotation_instr(pid, instr)
        elif isinstance(instr, core.ControlledRotationInstruction):
            return self._interpret_controlled_rotation_instr(pid, instr)
        elif isinstance(instr, core.ClassicalOpInstruction) or isinstance(
            instr, core.ClassicalOpModInstruction
        ):
            return self._interpret_binary_classical_instr(pid, instr)
        elif isinstance(instr, core.BreakpointInstruction):
            return self._interpret_breakpoint(pid, instr)
        else:
            raise RuntimeError(f"Invalid instruction {instr}")

    def _interpret_breakpoint(
        self, pid: int, instr: core.BreakpointInstruction
    ) -> None:
        if instr.action.value == 0:
            self._logger.info("BREAKPOINT: no action taken")
        elif instr.action.value == 1:
            self._logger.info("BREAKPOINT: dumping local state:")
            for i in range(self.qdevice.num_positions):
                if self.qdevice.mem_positions[i].in_use:
                    q = self.qdevice.peek(i, skip_noise=True)
                    qstate = qubitapi.reduced_dm(q)
                    self._logger.info(f"physical qubit {i}:\n{qstate}")

            GlobalSimData.get_quantum_state(save=True)  # TODO: rewrite this
        elif instr.action.value == 2:
            self._logger.info("BREAKPOINT: dumping global state:")
            if instr.role.value == 0:
                self._interface.send_netstack_msg(NetstackBreakpointCreateRequest(pid))
                ready = yield from self._interface.receive_netstack_msg()
                assert ready == "breakpoint ready"

                state = GlobalSimData.get_quantum_state(save=True)
                self._logger.info(state)

                self._interface.send_netstack_msg("breakpoint end")
                finished = yield from self._interface.receive_netstack_msg()
                assert finished == "breakpoint finished"
            elif instr.role.value == 1:
                self._interface.send_netstack_msg(NetstackBreakpointReceiveRequest(pid))
                ready = yield from self._interface.receive_netstack_msg()
                assert ready == "breakpoint ready"
                self._interface.send_netstack_msg("breakpoint end")
                finished = yield from self._interface.receive_netstack_msg()
                assert finished == "breakpoint finished"
            else:
                raise ValueError
        else:
            raise ValueError

    def _interpret_set(self, pid: int, instr: core.SetInstruction) -> None:
        self._logger.debug(f"Set register {instr.reg} to {instr.imm}")
        shared_mem = self._prog_mem().shared_mem
        shared_mem.set_reg_value(instr.reg, instr.imm.value)

    def _interpret_qalloc(self, pid: int, instr: core.QAllocInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem

        virt_id = shared_mem.get_reg_value(instr.reg)
        if virt_id is None:
            raise RuntimeError(f"qubit address in register {instr.reg} is not defined")
        self._logger.debug(f"Allocating qubit with virtual ID {virt_id}")

        phys_id = self.qdevice.allocate()
        shared_mem.map_virt_id(virt_id, phys_id)

    def _interpret_qfree(self, pid: int, instr: core.QFreeInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem

        virt_id = shared_mem.get_reg_value(instr.reg)
        assert virt_id is not None
        self._logger.debug(f"Freeing virtual qubit {virt_id}")
        phys_id = q_mem.phys_id_for(virt_id)
        assert phys_id is not None
        q_mem.unmap_virt_id(virt_id)
        self.qdevice.free(phys_id)
        self.send_signal(SIGNAL_MEMORY_FREED)
        self.qdevice.mem_positions[phys_id].in_use = False

    def _interpret_store(self, pid: int, instr: core.StoreInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem

        value = shared_mem.get_reg_value(instr.reg)
        if value is None:
            raise RuntimeError(f"value in register {instr.reg} is not defined")
        self._logger.debug(
            f"Storing value {value} from register {instr.reg} "
            f"to array entry {instr.entry}"
        )

        shared_mem.set_array_entry(instr.entry, value)

    def _interpret_load(self, pid: int, instr: core.LoadInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem

        value = shared_mem.get_array_entry(instr.entry)
        if value is None:
            raise RuntimeError(f"array value at {instr.entry} is not defined")
        self._logger.debug(
            f"Storing value {value} from array entry {instr.entry} "
            f"to register {instr.reg}"
        )

        shared_mem.set_reg_value(instr.reg, value)

    def _interpret_lea(self, pid: int, instr: core.LeaInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        self._logger.debug(
            f"Storing address of {instr.address} to register {instr.reg}"
        )
        shared_mem.set_reg_value(instr.reg, instr.address.address)

    def _interpret_undef(self, pid: int, instr: core.UndefInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        self._logger.debug(f"Unset array entry {instr.entry}")
        shared_mem.set_array_entry(instr.entry, None)

    def _interpret_array(self, pid: int, instr: core.ArrayInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem

        length = shared_mem.get_reg_value(instr.size)
        assert length is not None
        self._logger.debug(
            f"Initializing an array of length {length} at address {instr.address}"
        )

        shared_mem.init_new_array(instr.address.address, length)

    def _interpret_branch_instr(
        self,
        pid: int,
        instr: Union[
            core.BranchUnaryInstruction,
            core.BranchBinaryInstruction,
            core.JmpInstruction,
        ],
    ) -> None:
        shared_mem = self._prog_mem().shared_mem
        a, b = None, None
        registers = []
        if isinstance(instr, core.BranchUnaryInstruction):
            a = shared_mem.get_reg_value(instr.reg)
            registers = [instr.reg]
        elif isinstance(instr, core.BranchBinaryInstruction):
            a = shared_mem.get_reg_value(instr.reg0)
            b = shared_mem.get_reg_value(instr.reg1)
            registers = [instr.reg0, instr.reg1]

        if isinstance(instr, core.JmpInstruction):
            condition = True
        elif isinstance(instr, core.BranchUnaryInstruction):
            condition = instr.check_condition(a)
        elif isinstance(instr, core.BranchBinaryInstruction):
            condition = instr.check_condition(a, b)

        if condition:
            jump_address = instr.line
            self._logger.debug(
                f"Branching to line {jump_address}, since {instr}(a={a}, b={b}) "
                f"is True, with values from registers {registers}"
            )
            shared_mem.set_prog_counter(jump_address.value)
        else:
            self._logger.debug(
                f"Don't branch, since {instr}(a={a}, b={b}) "
                f"is False, with values from registers {registers}"
            )
            shared_mem.increment_prog_counter()

    def _interpret_binary_classical_instr(
        self,
        pid: int,
        instr: Union[
            core.ClassicalOpInstruction,
            core.ClassicalOpModInstruction,
        ],
    ) -> None:
        shared_mem = self._prog_mem().shared_mem
        mod = None
        if isinstance(instr, core.ClassicalOpModInstruction):
            mod = shared_mem.get_reg_value(instr.regmod)
        if mod is not None and mod < 1:
            raise RuntimeError(f"Modulus needs to be greater or equal to 1, not {mod}")
        a = shared_mem.get_reg_value(instr.regin0)
        b = shared_mem.get_reg_value(instr.regin1)
        assert a is not None
        assert b is not None
        value = self._compute_binary_classical_instr(instr, a, b, mod=mod)
        mod_str = "" if mod is None else f"(mod {mod})"
        self._logger.debug(
            f"Performing {instr} of a={a} and b={b} {mod_str} "
            f"and storing the value {value} at register {instr.regout}"
        )
        shared_mem.set_reg_value(instr.regout, value)

    def _compute_binary_classical_instr(
        self, instr: NetQASMInstruction, a: int, b: int, mod: Optional[int] = 1
    ) -> int:
        if isinstance(instr, core.AddInstruction):
            return a + b
        elif isinstance(instr, core.AddmInstruction):
            assert mod is not None
            return (a + b) % mod
        elif isinstance(instr, core.SubInstruction):
            return a - b
        elif isinstance(instr, core.SubmInstruction):
            assert mod is not None
            return (a - b) % mod
        else:
            raise ValueError(f"{instr} cannot be used as binary classical function")

    def _interpret_init(
        self, pid: int, instr: core.InitInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError

    def _do_single_rotation(
        self,
        pid: int,
        instr: core.RotationInstruction,
        ns_instr: NsInstr,
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.reg)
        phys_id = q_mem.phys_id_for(virt_id)
        angle = self._get_rotation_angle_from_operands(
            n=instr.angle_num.value,
            d=instr.angle_denom.value,
        )
        self._logger.debug(
            f"Performing {instr} with angle {angle} on virtual qubit "
            f"{virt_id} (physical ID: {phys_id})"
        )
        prog = QuantumProgram()
        prog.apply(ns_instr, qubit_indices=[phys_id], angle=angle)
        yield from self.qdevice.execute_program(prog)

    def _interpret_single_rotation_instr(
        self, pid: int, instr: nv.RotXInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError

    def _do_controlled_rotation(
        self,
        pid: int,
        instr: core.ControlledRotationInstruction,
        ns_instr: NsInstr,
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id0 = shared_mem.get_reg_value(instr.reg0)
        phys_id0 = q_mem.phys_id_for(virt_id0)
        virt_id1 = shared_mem.get_reg_value(instr.reg1)
        phys_id1 = q_mem.phys_id_for(virt_id1)
        angle = self._get_rotation_angle_from_operands(
            n=instr.angle_num.value,
            d=instr.angle_denom.value,
        )
        self._logger.debug(
            f"Performing {instr} with angle {angle} on virtual qubits "
            f"{virt_id0} and {virt_id1} (physical IDs: {phys_id0} and {phys_id1})"
        )
        prog = QuantumProgram()
        prog.apply(ns_instr, qubit_indices=[phys_id0, phys_id1], angle=angle)
        yield from self.qdevice.execute_program(prog)

    def _interpret_controlled_rotation_instr(
        self, pid: int, instr: core.ControlledRotationInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError

    def _get_rotation_angle_from_operands(self, n: int, d: int) -> float:
        return float(n * PI / (2**d))

    def _interpret_meas(
        self, pid: int, instr: core.MeasInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError

    def _interpret_create_epr(self, pid: int, instr: core.CreateEPRInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        remote_node_id = shared_mem.get_reg_value(instr.remote_node_id)
        epr_socket_id = shared_mem.get_reg_value(instr.epr_socket_id)
        qubit_array_addr = shared_mem.get_reg_value(instr.qubit_addr_array)
        arg_array_addr = shared_mem.get_reg_value(instr.arg_array)
        result_array_addr = shared_mem.get_reg_value(instr.ent_results_array)
        assert remote_node_id is not None
        assert epr_socket_id is not None
        # qubit_array_addr can be None
        assert arg_array_addr is not None
        assert result_array_addr is not None
        self._logger.debug(
            f"Creating EPR pair with remote node id {remote_node_id} "
            f"and EPR socket ID {epr_socket_id}, "
            f"using qubit addresses stored in array with address {qubit_array_addr}, "
            f"using arguments stored in array with address {arg_array_addr}, "
            f"placing the entanglement information in array at "
            f"address {result_array_addr}"
        )

        msg = NetstackCreateRequest(
            pid,
            remote_node_id,
            epr_socket_id,
            qubit_array_addr,
            arg_array_addr,
            result_array_addr,
        )
        self._interface.send_netstack_msg(msg)
        # result = yield from self._interface.receive_netstack_msg()
        # self._logger.debug(f"result from netstack: {result}")

    def _interpret_recv_epr(self, pid: int, instr: core.RecvEPRInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        remote_node_id = shared_mem.get_reg_value(instr.remote_node_id)
        epr_socket_id = shared_mem.get_reg_value(instr.epr_socket_id)
        qubit_array_addr = shared_mem.get_reg_value(instr.qubit_addr_array)
        result_array_addr = shared_mem.get_reg_value(instr.ent_results_array)
        assert remote_node_id is not None
        assert epr_socket_id is not None
        # qubit_array_addr can be None
        assert result_array_addr is not None
        self._logger.debug(
            f"Receiving EPR pair with remote node id {remote_node_id} "
            f"and EPR socket ID {epr_socket_id}, "
            f"using qubit addresses stored in array with address {qubit_array_addr}, "
            f"placing the entanglement information in array at "
            f"address {result_array_addr}"
        )

        msg = NetstackReceiveRequest(
            pid,
            remote_node_id,
            epr_socket_id,
            qubit_array_addr,
            result_array_addr,
        )
        self._interface.send_netstack_msg(msg)
        # result = yield from self._interface.receive_netstack_msg()
        # self._logger.debug(f"result from netstack: {result}")

    def _interpret_wait_all(
        self, pid: int, instr: core.WaitAllInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        self._logger.debug(
            f"Waiting for all entries in array slice {instr.slice} to become defined"
        )
        assert isinstance(instr.slice.start, Register)
        assert isinstance(instr.slice.stop, Register)
        start: int = shared_mem.get_reg_value(instr.slice.start)
        end: int = shared_mem.get_reg_value(instr.slice.stop)
        addr: int = instr.slice.address.address

        self._logger.debug(
            f"checking if @{addr}[{start}:{end}] has values for app ID {pid}"
        )

        while True:
            values = self._prog_mem().get_array_values(addr, start, end)
            if any(v is None for v in values):
                self._logger.debug(
                    f"waiting for netstack to write to @{addr}[{start}:{end}] "
                    f"for app ID {pid}"
                )
                yield from self._interface.receive_netstack_msg()
                self._logger.debug("netstack wrote something")
            else:
                break
        self._interface.flush_netstack_msgs()
        self._logger.debug("all entries were written")

        self._logger.info(f"\nFinished waiting for array slice {instr.slice}")

    def _interpret_ret_reg(self, pid: int, instr: core.RetRegInstruction) -> None:
        pass

    def _interpret_ret_arr(self, pid: int, instr: core.RetArrInstruction) -> None:
        pass

    def _interpret_single_qubit_instr(
        self, pid: int, instr: core.SingleQubitInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError

    def _interpret_two_qubit_instr(
        self, pid: int, instr: core.SingleQubitInstruction
    ) -> Generator[EventExpression, None, None]:
        raise NotImplementedError


class GenericProcessor(QnosProcessor):
    """A `Processor` for nodes with a generic quantum hardware."""

    def _interpret_init(
        self, pid: int, instr: core.InitInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.reg)
        phys_id = q_mem.phys_id_for(virt_id)
        self._logger.debug(
            f"Performing {instr} on virtual qubit "
            f"{virt_id} (physical ID: {phys_id})"
        )
        prog = QuantumProgram()
        prog.apply(INSTR_INIT, qubit_indices=[phys_id])
        yield from self.qdevice.execute_program(prog)

    def _interpret_meas(
        self, pid: int, instr: core.MeasInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.qreg)
        phys_id = q_mem.phys_id_for(virt_id)

        self._logger.debug(
            f"Measuring qubit {virt_id} (physical ID: {phys_id}), "
            f"placing the outcome in register {instr.creg}"
        )

        prog = QuantumProgram()
        prog.apply(INSTR_MEASURE, qubit_indices=[phys_id])
        yield from self.qdevice.execute_program(prog)
        outcome: int = prog.output["last"][0]
        shared_mem.set_reg_value(instr.creg, outcome)

    def _interpret_single_qubit_instr(
        self, pid: int, instr: core.SingleQubitInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.qreg)
        phys_id = q_mem.phys_id_for(virt_id)
        if isinstance(instr, vanilla.GateXInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_X, qubit_indices=[phys_id])
            yield from self.qdevice.execute_program(prog)
        elif isinstance(instr, vanilla.GateYInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_Y, qubit_indices=[phys_id])
            yield from self.qdevice.execute_program(prog)
        elif isinstance(instr, vanilla.GateZInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_Z, qubit_indices=[phys_id])
            yield from self.qdevice.execute_program(prog)
        elif isinstance(instr, vanilla.GateHInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_H, qubit_indices=[phys_id])
            yield from self.qdevice.execute_program(prog)
        else:
            raise RuntimeError(f"Unsupported instruction {instr}")

    def _interpret_single_rotation_instr(
        self, pid: int, instr: nv.RotXInstruction
    ) -> Generator[EventExpression, None, None]:
        if isinstance(instr, vanilla.RotXInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_X)
        elif isinstance(instr, vanilla.RotYInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_Y)
        elif isinstance(instr, vanilla.RotZInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_Z)
        else:
            raise RuntimeError(f"Unsupported instruction {instr}")

    def _interpret_controlled_rotation_instr(
        self, pid: int, instr: core.ControlledRotationInstruction
    ) -> Generator[EventExpression, None, None]:
        raise RuntimeError(f"Unsupported instruction {instr}")

    def _interpret_two_qubit_instr(
        self, pid: int, instr: core.SingleQubitInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id0 = shared_mem.get_reg_value(instr.reg0)
        phys_id0 = q_mem.phys_id_for(virt_id0)
        virt_id1 = shared_mem.get_reg_value(instr.reg1)
        phys_id1 = q_mem.phys_id_for(virt_id1)
        if isinstance(instr, vanilla.CnotInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_CNOT, qubit_indices=[phys_id0, phys_id1])
            yield from self.qdevice.execute_program(prog)
        elif isinstance(instr, vanilla.CphaseInstruction):
            prog = QuantumProgram()
            prog.apply(INSTR_CZ, qubit_indices=[phys_id0, phys_id1])
            yield from self.qdevice.execute_program(prog)
        else:
            raise RuntimeError(f"Unsupported instruction {instr}")


class NVProcessor(QnosProcessor):
    """A `Processor` for nodes with a NV hardware."""

    def _interpret_qalloc(self, pid: int, instr: core.QAllocInstruction) -> None:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem

        virt_id = shared_mem.get_reg_value(instr.reg)
        if virt_id is None:
            raise RuntimeError(f"qubit address in register {instr.reg} is not defined")
        self._logger.debug(f"Allocating qubit with virtual ID {virt_id}")

        # Virtual ID > 0 corresponds to memory qubits
        if virt_id > 0:
            phys_id = self.qdevice.allocate_mem()
        else:
            phys_id = self.qdevice.allocate_comm()
        q_mem.map_virt_id(virt_id, phys_id)

    def _interpret_init(
        self, pid: int, instr: core.InitInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.reg)
        phys_id = q_mem.phys_id_for(virt_id)
        self._logger.debug(
            f"Performing {instr} on virtual qubit "
            f"{virt_id} (physical ID: {phys_id})"
        )
        prog = QuantumProgram()
        prog.apply(INSTR_INIT, qubit_indices=[phys_id])
        yield from self.qdevice.execute_program(prog)

    def _measure_electron(self) -> Generator[EventExpression, None, int]:
        prog = QuantumProgram()
        prog.apply(INSTR_MEASURE, qubit_indices=[0])
        yield from self.qdevice.execute_program(prog)
        outcome: int = prog.output["last"][0]
        return outcome

    def _move_carbon_to_electron_for_measure(
        self, carbon_id: int
    ) -> Generator[EventExpression, None, None]:
        prog = QuantumProgram()
        prog.apply(INSTR_INIT, qubit_indices=[0])
        prog.apply(INSTR_ROT_Y, qubit_indices=[0], angle=PI_OVER_2)
        prog.apply(INSTR_CYDIR, qubit_indices=[0, carbon_id], angle=-PI_OVER_2)
        prog.apply(INSTR_ROT_X, qubit_indices=[0], angle=-PI_OVER_2)
        prog.apply(INSTR_CXDIR, qubit_indices=[0, carbon_id], angle=PI_OVER_2)
        prog.apply(INSTR_ROT_Y, qubit_indices=[0], angle=-PI_OVER_2)
        yield from self.qdevice.execute_program(prog)

    def _move_electron_to_carbon(
        self, carbon_id: int
    ) -> Generator[EventExpression, None, None]:
        prog = QuantumProgram()
        prog.apply(INSTR_INIT, qubit_indices=[carbon_id])
        prog.apply(INSTR_ROT_Y, qubit_indices=[0], angle=PI_OVER_2)
        prog.apply(INSTR_CYDIR, qubit_indices=[0, carbon_id], angle=-PI_OVER_2)
        prog.apply(INSTR_ROT_X, qubit_indices=[0], angle=-PI_OVER_2)
        prog.apply(INSTR_CXDIR, qubit_indices=[0, carbon_id], angle=PI_OVER_2)
        yield from self.qdevice.execute_program(prog)

    def _interpret_meas(
        self, pid: int, instr: core.MeasInstruction
    ) -> Generator[EventExpression, None, None]:
        shared_mem = self._prog_mem().shared_mem
        q_mem = self._prog_mem().quantum_mem
        virt_id = shared_mem.get_reg_value(instr.qreg)
        phys_id = q_mem.phys_id_for(virt_id)

        # Only the electron (phys ID 0) can be measured.
        # Measuring any other physical qubit (i.e one of the carbons) requires
        # freeing up the electron and moving the target qubit to the electron first.

        if phys_id == 0:
            # Measuring the electron. This can be done immediately.
            outcome = yield from self._measure_electron()
            shared_mem.set_reg_value(instr.creg, outcome)
        else:
            # We want to measure a carbon.
            # Move it to the electron first.
            if self.qdevice.is_allocated(0):
                # Electron is already allocated. Try to move it to a free carbon.
                try:
                    new_qubit = self.qdevice.allocate()
                except AllocError:
                    self._logger.error(
                        f"Allocation error. Reason:\n"
                        f"Measuring virtual qubit {virt_id}.\n"
                        f"-> Measuring physical qubit {phys_id}.\n"
                        f"-> Measuring physical qubit with ID > 0 requires "
                        f"physical qubit 0 to be free."
                        f"-> Physical qubit 0 is in use.\n"
                        f"-> Trying to find free physical qubit for qubit 0.\n"
                        f"-> No physical qubits available."
                    )
                yield from self._move_electron_to_carbon(new_qubit)
                elec_pid, elec_virt_id = self._qnos.get_virt_qubit_for_phys_id(0)
                self._logger.warning(
                    f"moving virtual qubit {elec_virt_id} from app "
                    f"{pid} from physical ID 0 to {new_qubit}"
                )
                # Update qubit ID mapping.
                # TODO: fix this
                self.program_memories[elec_pid].unmap_virt_id(elec_virt_id)
                self.program_memories[elec_pid].map_virt_id(elec_virt_id, new_qubit)
                q_mem.unmap_virt_id(virt_id)
                q_mem.map_virt_id(virt_id, 0)
                yield from self._move_carbon_to_electron_for_measure(phys_id)
                self.qdevice.free(phys_id)
                self.send_signal(SIGNAL_MEMORY_FREED)
                self.qdevice.set_mem_pos_in_use(phys_id, False)
                outcome = yield from self._measure_electron()
                shared_mem.set_reg_value(instr.creg, outcome)
            else:
                self.qdevice.allocate_comm()
                q_mem.unmap_virt_id(virt_id)
                q_mem.map_virt_id(virt_id, 0)
                yield from self._move_carbon_to_electron_for_measure(phys_id)
                self.qdevice.free(phys_id)
                self.send_signal(SIGNAL_MEMORY_FREED)
                self.qdevice.set_mem_pos_in_use(phys_id, False)
                outcome = yield from self._measure_electron()
                shared_mem.set_reg_value(instr.creg, outcome)

        self._logger.debug(
            f"Measuring qubit {virt_id} (physical ID: {phys_id}), "
            f"placing the outcome in register {instr.creg}"
        )

    def _interpret_single_rotation_instr(
        self, pid: int, instr: nv.RotXInstruction
    ) -> Generator[EventExpression, None, None]:
        if isinstance(instr, nv.RotXInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_X)
        elif isinstance(instr, nv.RotYInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_Y)
        elif isinstance(instr, nv.RotZInstruction):
            yield from self._do_single_rotation(pid, instr, INSTR_ROT_Z)
        else:
            raise RuntimeError(f"Unsupported instruction {instr}")

    def _interpret_controlled_rotation_instr(
        self, pid: int, instr: core.ControlledRotationInstruction
    ) -> Generator[EventExpression, None, None]:
        if isinstance(instr, nv.ControlledRotXInstruction):
            yield from self._do_controlled_rotation(pid, instr, INSTR_CXDIR)
        elif isinstance(instr, nv.ControlledRotYInstruction):
            yield from self._do_controlled_rotation(pid, instr, INSTR_CYDIR)
        else:
            raise RuntimeError(f"Unsupported instruction {instr}")
