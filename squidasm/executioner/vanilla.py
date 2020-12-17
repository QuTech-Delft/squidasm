from netsquid.components.instructions import (
    INSTR_INIT,
    INSTR_X,
    INSTR_Y,
    INSTR_Z,
    INSTR_H,
    INSTR_K,
    INSTR_S,
    INSTR_T,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_CNOT,
    INSTR_CZ,
    INSTR_SWAP,
)

from squidasm.executioner.base import NetSquidExecutioner
from netqasm.lang.instr import vanilla, core


VANILLA_NS_INSTR_MAPPING = {
    core.InitInstruction: INSTR_INIT,
    vanilla.GateXInstruction: INSTR_X,
    vanilla.GateYInstruction: INSTR_Y,
    vanilla.GateZInstruction: INSTR_Z,
    vanilla.GateHInstruction: INSTR_H,
    vanilla.GateKInstruction: INSTR_K,
    vanilla.GateSInstruction: INSTR_S,
    vanilla.GateTInstruction: INSTR_T,
    vanilla.RotXInstruction: INSTR_ROT_X,
    vanilla.RotYInstruction: INSTR_ROT_Y,
    vanilla.RotZInstruction: INSTR_ROT_Z,
    vanilla.CnotInstruction: INSTR_CNOT,
    vanilla.CphaseInstruction: INSTR_CZ,
    vanilla.MovInstruction: INSTR_SWAP,
}


class VanillaNetSquidExecutioner(NetSquidExecutioner):
    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None,
                 flavour=None, instr_proc_time=0, host_latency=0):
        """Represents a QNodeOS processor that communicates with a QDevice that supports vanilla instructions"""
        super().__init__(node, name, network_stack, instr_log_dir,
                         instr_mapping=VANILLA_NS_INSTR_MAPPING, instr_proc_time=instr_proc_time,
                         host_latency=host_latency)
