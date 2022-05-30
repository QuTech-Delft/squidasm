from __future__ import annotations

import math
from typing import List

from netqasm.lang.operand import Template
from netqasm.sdk.qubit import Qubit

from squidasm.run.qoala import lhr as lp
from squidasm.run.stack.config import (
    LinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramContext, ProgramMeta


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

        epr = epr_socket.create_keep()[0]

        epr.rot_Z(angle=self._theta1)
        epr.H()
        p1 = epr.measure(store_array=True)

        subrt = conn.compile()
        subroutines = {"subrt": subrt}

        lhr_subrt = lp.LhrSubroutine(subrt, return_map={"p1": lp.LhrSharedMemLoc("M0")})
        instrs: List[lp.ClassicalLhrOp] = []
        instrs.append(lp.RunSubroutineOp(lp.LhrVector([]), lhr_subrt))
        instrs.append(lp.AssignCValueOp("p1", p1))

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


class ServerProgram(lp.SdkProgram):
    PEER = "client"

    def __init__(self) -> None:
        pass

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile(self, context: ProgramContext) -> lp.LhrProgram:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Create EPR Pair
        epr = epr_socket.recv_keep()[0]
        q = Qubit(conn)
        q.H()

        epr.cphase(q)

        subrt1 = conn.compile()
        subroutines = {"subrt1": subrt1}

        instrs: List[lp.ClassicalLhrOp] = []
        lhr_subrt1 = lp.LhrSubroutine(subrt1, return_map={})
        instrs.append(lp.RunSubroutineOp(lp.LhrVector([]), lhr_subrt1))

        instrs.append(lp.ReceiveCMsgOp("delta1"))

        epr.rot_Z(n=Template("delta1"), d=4)
        epr.H()
        m1 = epr.measure(store_array=False)

        subrt2 = conn.compile()
        subroutines["subrt2"] = subrt2

        lhr_subrt2 = lp.LhrSubroutine(
            subrt2, return_map={"m1": lp.LhrSharedMemLoc("M0")}
        )
        instrs.append(lp.RunSubroutineOp(lp.LhrVector(["delta1"]), lhr_subrt2))
        instrs.append(lp.AssignCValueOp("m1", m1))
        instrs.append(lp.SendCMsgOp("m1"))

        instrs.append(lp.ReceiveCMsgOp("delta2"))

        q.rot_Z(n=Template("delta2"), d=4)
        q.H()
        m2 = q.measure(store_array=False)
        subrt3 = conn.compile()
        subroutines["subrt3"] = subrt3

        lhr_subrt3 = lp.LhrSubroutine(
            subrt3, return_map={"m2": lp.LhrSharedMemLoc("M0")}
        )
        instrs.append(lp.RunSubroutineOp(lp.LhrVector(["delta2"]), lhr_subrt3))
        instrs.append(lp.AssignCValueOp("m2", m2))
        instrs.append(lp.ReturnResultOp("m1"))
        instrs.append(lp.ReturnResultOp("m2"))

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
    server_program = ServerProgram()

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

    LogManager.set_log_level("WARNING")
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
