from __future__ import annotations

import math
import os
import re
from pipes import Template
from typing import Any, Dict, Generator, List, Tuple

from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.lang.operand import Register, RegisterName, Template
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state

from pydynaa import EventExpression
from squidasm.run.stack import lhrprogram as lp
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.connection import QnosConnection
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(lp.SdkProgram):
    PEER = "server"

    def __init__(
        self,
        alpha: float,
        beta: float,
        theta1: float,
        r1: int,
    ):
        self._alpha = alpha
        self._beta = beta
        self._theta1 = theta1
        self._r1 = r1

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={
                "alpha": self._alpha,
                "beta": self._beta,
                "theta1": self._theta1,
                "r1": self._r1,
            },
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile(self, context: ProgramContext) -> lp.LhrProgram:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        epr = epr_socket.create_keep()[0]

        epr.rot_Z(angle=self._theta1)
        epr.H()
        p1 = epr.measure(store_array=True)

        subrt = conn.compile()
        subroutines = {"subrt": subrt}

        lhr_subrt = lp.LhrSubroutine(subrt, return_map={"p1": lp.LhrSharedMemLoc("M0")})
        instrs: List[lp.ClassicalLirOp] = []
        instrs.append(lp.RunSubroutineOp(lp.LhrVector([]), lhr_subrt))
        # instrs.append(lp.AssignCValueOp("p1", p1))

        delta1 = self._alpha - self._theta1 + self._r1 * math.pi
        delta1_discrete = delta1 / (math.pi / 16)

        instrs.append(lp.AssignCValueOp("delta1", delta1_discrete))
        instrs.append(lp.MultiplyConstantCValueOp("p1", "p1", 16))
        instrs.append(lp.AddCValueOp("delta1", "delta1", "p1"))
        instrs.append(lp.SendCMsgOp("delta1"))

        instrs.append(lp.ReceiveCMsgOp("m1"))

        beta = math.pow(-1, self._r1) * self._beta
        delta2_discrete = beta / (math.pi / 16)
        instrs.append(lp.AssignCValueOp("delta2", delta2_discrete))
        instrs.append(
            lp.BitConditionalMultiplyConstantCValueOp(
                result="delta2", value0="delta2", value1=-1, cond="m1"
            )
        )
        instrs.append(lp.SendCMsgOp("delta2"))

        instrs.append(lp.ReturnResultOp("p1"))

        return lp.LhrProgram(instrs, subroutines, meta=self.meta)


PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        theta1=theta1,
        r1=0,
    )
    # server_program = ServerProgram()
    lhr_file = os.path.join(os.path.dirname(__file__), "bqc_5_5.lhr")
    with open(lhr_file) as file:
        lhr_text = file.read()
    server_program = lp.LhrParser(lhr_text).parse()
    server_program.meta = ProgramMeta(
        name="server_program",
        parameters={},
        csockets=["client"],
        epr_sockets=["client"],
        max_qubits=2,
    )

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


if __name__ == "__main__":
    num_times = 1

    LogManager.set_log_level("DEBUG")
    LogManager.log_to_file("dump.log")

    sender_stack = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    receiver_stack = StackConfig(
        name="server",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
