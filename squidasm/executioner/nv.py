from netsquid.components.instructions import (
    INSTR_INIT,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
)

import netsquid.qubits.operators as ops
from netsquid.components.instructions import IGate

from squidasm.executioner.base import NetSquidExecutioner
from netqasm.instructions import nv, core


CSQX = ops.Rx90.ctrl
INSTR_CSQX = IGate("csqx_gate", CSQX)

NV_NS_INSTR_MAPPING = {
    core.InitInstruction: INSTR_INIT,
    nv.RotXInstruction: INSTR_ROT_X,
    nv.RotYInstruction: INSTR_ROT_Y,
    nv.RotZInstruction: INSTR_ROT_Z,
    nv.CSqrtXInstruction: INSTR_CSQX
}


class NVNetSquidExecutioner(NetSquidExecutioner):
    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None, flavour=None):
        """Represents a QNodeOS processor that communicates with a QDevice that supports NV instructions"""
        super().__init__(node, name, network_stack, instr_log_dir, instr_mapping=NV_NS_INSTR_MAPPING)
