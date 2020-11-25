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
    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None, flavour=None):
        """Represents a QNodeOS processor that communicates with a QDevice that supports NV instructions"""
        super().__init__(node, name, network_stack, instr_log_dir, instr_mapping=NV_NS_INSTR_MAPPING)

    def _do_meas(self, subroutine_id, q_address):
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        assert position == 0, "Can only measure the electron directly"
        super()._do_meas(
            subroutine_id=subroutine_id,
            q_address=q_address,
        )
