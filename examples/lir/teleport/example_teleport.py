from __future__ import annotations

import math
from typing import List

from netqasm.lang.operand import Template
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state

from squidasm.qoala.lang import lhr as lp
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramContext, ProgramMeta


class SenderProgram(lp.SdkProgram):
    PEER = "receiver"

    def __init__(
        self,
        theta: float,
        phi: float,
    ):
        self._theta = theta
        self._phi = phi

        super().__init__([], {})

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="sender_program",
            parameters={
                "theta": self._theta,
                "phi": self._phi,
            },
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile(self, context: ProgramContext) -> lp.LhrProgram:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        q = Qubit(conn)
        set_qubit_state(q, self._phi, self._theta)

        e = epr_socket.create_keep()[0]
        q.cnot(e)
        q.H()
        m1 = q.measure()
        m2 = e.measure()

        subrt = conn.compile()
        subroutines = {"subrt": subrt}

        instrs: List[lp.ClassicalLhrOp] = []
        instrs.append(lp.RunSubroutineOp("subrt"))
        instrs.append(lp.AssignCValueOp("m1", m1))
        instrs.append(lp.AssignCValueOp("m2", m2))
        instrs.append(lp.SendCMsgOp("m1"))
        instrs.append(lp.SendCMsgOp("m2"))
        instrs.append(lp.ReturnResultOp("m1"))
        instrs.append(lp.ReturnResultOp("m2"))

        self.instructions = instrs
        self.subroutines = subroutines
        return lp.LhrProgram(instrs, subroutines, self.meta)


class ReceiverProgram(lp.SdkProgram):
    PEER = "sender"

    def __init__(self) -> None:
        super().__init__([], {})

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="receiver_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def compile(self, context: ProgramContext) -> lp.LhrProgram:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        e = epr_socket.recv_keep()[0]
        subrt1 = conn.compile()

        subroutines = {"subrt1": subrt1}

        instrs: List[lp.ClassicalLhrOp] = []
        instrs.append(lp.RunSubroutineOp("subrt1"))
        instrs.append(lp.ReceiveCMsgOp("m1"))
        instrs.append(lp.ReceiveCMsgOp("m2"))

        m1 = conn.builder.new_register(init_value=Template("m1"), return_reg=False)
        m2 = conn.builder.new_register(init_value=Template("m2"), return_reg=False)

        with m2.if_eq(1):
            e.X()
        with m1.if_eq(1):
            e.Z()

        m = e.measure(store_array=False)

        subrt2 = conn.compile()
        subroutines["subrt2"] = subrt2

        instrs.append(lp.RunSubroutineOp("subrt2"))
        instrs.append(lp.AssignCValueOp("m", m))
        instrs.append(lp.ReturnResultOp("m"))

        self.instructions = instrs
        self.subroutines = subroutines
        return lp.LhrProgram(instrs, subroutines, self.meta)


if __name__ == "__main__":
    LogManager.set_log_level("INFO")

    sender_stack = StackConfig(
        name="sender",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    receiver_stack = StackConfig(
        name="receiver",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="sender",
        stack2="receiver",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    sender_program = SenderProgram(theta=math.pi, phi=0)
    receiver_program = ReceiverProgram()

    results = run(cfg, {"sender": sender_program, "receiver": receiver_program})
    print(results)
