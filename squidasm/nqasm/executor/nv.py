from typing import Dict, Generator, Optional

import numpy as np
from netqasm.lang import instr as ins
from netqasm.lang.instr import core, nv
from netqasm.lang.instr.flavour import Flavour
from netsquid.components import Instruction as NetSquidInstruction
from netsquid.components.instructions import (
    INSTR_CXDIR,
    INSTR_CYDIR,
    INSTR_INIT,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
)
from netsquid.nodes.node import Node as NetSquidNode

from pydynaa import EventExpression
from squidasm.nqasm.executor.base import NetSquidExecutor

T_InstrMap = Dict[ins.NetQASMInstruction, NetSquidInstruction]

NV_NS_INSTR_MAPPING: T_InstrMap = {
    core.InitInstruction: INSTR_INIT,
    nv.RotXInstruction: INSTR_ROT_X,
    nv.RotYInstruction: INSTR_ROT_Y,
    nv.RotZInstruction: INSTR_ROT_Z,
    nv.ControlledRotXInstruction: INSTR_CXDIR,
    nv.ControlledRotYInstruction: INSTR_CYDIR,
}


class NVNetSquidExecutor(NetSquidExecutor):
    def __init__(
        self,
        node: NetSquidNode,
        name: Optional[str] = None,
        instr_log_dir: Optional[str] = None,
        flavour: Optional[Flavour] = None,
        instr_proc_time: int = 0,
        host_latency: int = 0,
    ) -> None:
        """Represents a QNodeOS processor that communicates with a QDevice that supports NV instructions"""
        super().__init__(
            node,
            name,
            instr_log_dir,
            instr_mapping=NV_NS_INSTR_MAPPING,
            instr_proc_time=instr_proc_time,
            host_latency=host_latency,
        )

    def _do_meas(
        self, subroutine_id: int, q_address: int
    ) -> Generator[EventExpression, None, int]:
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        if position != 0:  # a carbon
            # Move the state to the electron (position=0) first and then measure the electron.
            # See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
            # for the circuit.
            self._logger.debug(
                f"Moving qubit from carbon (position {position}) to electron before measuring"
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_INIT, qubit_mapping=[0]
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_ROT_Y, qubit_mapping=[0], angle=np.pi / 2
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_CYDIR, qubit_mapping=[0, position], angle=-np.pi / 2
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_ROT_X, qubit_mapping=[0], angle=-np.pi / 2
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_CXDIR, qubit_mapping=[0, position], angle=np.pi / 2
            )
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_ROT_Y, qubit_mapping=[0], angle=-np.pi / 2
            )

            # Explicitly free physical qubit 0, since the Executor will
            # only free the original qubit.
            self._clear_phys_qubit_in_memory(0)

        # Measure the electron.
        outcome = yield from super()._meas_physical_qubit(0)
        return outcome
