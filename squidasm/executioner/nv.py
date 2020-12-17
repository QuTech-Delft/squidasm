import numpy as np

from netsquid.components.instructions import (
    INSTR_INIT,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_CXDIR,
    INSTR_CYDIR
)

from squidasm.executioner.base import NetSquidExecutioner
from netqasm.lang.instr import nv, core


NV_NS_INSTR_MAPPING = {
    core.InitInstruction: INSTR_INIT,
    nv.RotXInstruction: INSTR_ROT_X,
    nv.RotYInstruction: INSTR_ROT_Y,
    nv.RotZInstruction: INSTR_ROT_Z,
    nv.ControlledRotXInstruction: INSTR_CXDIR,
    nv.ControlledRotYInstruction: INSTR_CYDIR,
}


class NVNetSquidExecutioner(NetSquidExecutioner):
    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None,
                 flavour=None, instr_proc_time=0, host_latency=0):
        """Represents a QNodeOS processor that communicates with a QDevice that supports NV instructions"""
        super().__init__(node, name, network_stack, instr_log_dir, instr_mapping=NV_NS_INSTR_MAPPING,
                         instr_proc_time=instr_proc_time, host_latency=host_latency)

    def _do_meas(self, subroutine_id, q_address):
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        if position != 0:  # a carbon
            # Move the state to the electron (position=0) first and then measure the electron.
            # See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
            # for the circuit.
            self._logger.debug(f"Moving qubit from carbon (position {position}) to electron before measuring")
            yield from self._execute_qdevice_instruction(ns_instr=INSTR_INIT, qubit_mapping=[0])
            yield from self._execute_qdevice_instruction(ns_instr=INSTR_ROT_Y, qubit_mapping=[0], angle=np.pi/2)
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_CYDIR, qubit_mapping=[0, position], angle=-np.pi/2)
            yield from self._execute_qdevice_instruction(ns_instr=INSTR_ROT_X, qubit_mapping=[0], angle=-np.pi/2)
            yield from self._execute_qdevice_instruction(
                ns_instr=INSTR_CXDIR, qubit_mapping=[0, position], angle=np.pi/2)
            yield from self._execute_qdevice_instruction(ns_instr=INSTR_ROT_Y, qubit_mapping=[0], angle=-np.pi/2)

        # Measure the electron.
        outcome = yield from super()._meas_physical_qubit(0)
        return outcome
