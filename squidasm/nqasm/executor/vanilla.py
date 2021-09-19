from typing import Dict, Optional

from netqasm.lang import instr as ins
from netqasm.lang.instr import core, vanilla
from netqasm.lang.instr.flavour import Flavour
from netsquid.components import Instruction as NetSquidInstruction
from netsquid.components.instructions import (
    INSTR_CNOT,
    INSTR_CZ,
    INSTR_H,
    INSTR_INIT,
    INSTR_K,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_S,
    INSTR_SWAP,
    INSTR_T,
    INSTR_X,
    INSTR_Y,
    INSTR_Z,
)
from netsquid.nodes.node import Node as NetSquidNode

from squidasm.nqasm.executor.base import NetSquidExecutor

T_InstrMap = Dict[ins.NetQASMInstruction, NetSquidInstruction]

VANILLA_NS_INSTR_MAPPING: T_InstrMap = {
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


class VanillaNetSquidExecutor(NetSquidExecutor):
    def __init__(
        self,
        node: NetSquidNode,
        name: Optional[str] = None,
        instr_log_dir: Optional[str] = None,
        flavour: Optional[Flavour] = None,
        instr_proc_time: int = 0,
        host_latency: int = 0,
    ):
        """Represents a QNodeOS processor that communicates with a QDevice that supports vanilla instructions"""
        super().__init__(
            node,
            name,
            instr_log_dir,
            instr_mapping=VANILLA_NS_INSTR_MAPPING,
            instr_proc_time=instr_proc_time,
            host_latency=host_latency,
        )
