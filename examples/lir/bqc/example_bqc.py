from __future__ import annotations

import math
from typing import List

from netqasm.lang.operand import Template

from squidasm.run.stack import lhrprogram as lp
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.program import ProgramContext, ProgramMeta


class ClientProgram(lp.LirProgram):
    PEER = "server"

    def __init__(
        self,
        alpha: float,
        beta: float,
        trap: bool,
        dummy: int,
        theta1: float,
        theta2: float,
        r1: int,
        r2: int,
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2

        super().__init__([], {})

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={
                "alpha": self._alpha,
                "beta": self._beta,
                "trap": self._trap,
                "dummy": self._dummy,
                "theta1": self._theta1,
                "theta2": self._theta2,
                "r1": self._r1,
                "r2": self._r2,
            },
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile(self, context: ProgramContext) -> None:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Create EPR pair
        epr1 = epr_socket.create_keep()[0]

        # RSP
        if self._trap and self._dummy == 2:
            # remotely-prepare a dummy state
            p2 = epr1.measure(store_array=False)
        else:
            epr1.rot_Z(angle=self._theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)

        # Create EPR pair
        epr2 = epr_socket.create_keep()[0]

        # RSP
        if self._trap and self._dummy == 1:
            # remotely-prepare a dummy state
            p1 = epr2.measure(store_array=False)
        else:
            epr2.rot_Z(angle=self._theta1)
            epr2.H()
            p1 = epr2.measure(store_array=False)

        subrt = conn.compile()
        subroutines = {"subrt": subrt}

        instrs: List[lp.ClassicalLirOp] = []
        instrs.append(lp.RunSubroutineOp("subrt"))
        instrs.append(lp.AssignCValueOp("p1", p1))
        instrs.append(lp.AssignCValueOp("p2", p2))

        if self._trap and self._dummy == 2:
            delta1 = -self._theta1 + self._r1 * math.pi
        else:
            delta1 = self._alpha - self._theta1 + self._r1 * math.pi
        delta1_discrete = delta1 / (math.pi / 16)

        instrs.append(lp.AssignCValueOp("delta1", delta1_discrete))
        instrs.append(lp.MultiplyConstantCValueOp("p1", "p1", 16))
        instrs.append(lp.AddCValueOp("delta1", "delta1", "p1"))
        instrs.append(lp.SendCMsgOp("delta1"))

        instrs.append(lp.ReceiveCMsgOp("m1"))

        if self._trap and self._dummy == 1:
            delta2 = -self._theta2 + self._r2 * math.pi
            delta2_discrete = delta2 / (math.pi / 16)
            instrs.append(lp.AssignCValueOp("delta2", delta2_discrete))
        else:
            beta = math.pow(-1, self._r1) * self._beta
            beta_discrete = beta / (math.pi / 16)
            instrs.append(lp.AssignCValueOp("beta", beta_discrete))
            instrs.append(
                lp.BitConditionalMultiplyConstantCValueOp(
                    result="beta", value0="beta", value1=16, cond="m1"
                )
            )
            delta2 = self._theta2 + self._r2 * math.pi
            delta2_discrete = delta2 / (math.pi / 16)
            instrs.append(lp.AssignCValueOp("delta2", delta2_discrete))
            instrs.append(lp.AddCValueOp("delta2", "delta2", "beta"))

        instrs.append(lp.MultiplyConstantCValueOp("p2", "p2", 16))
        instrs.append(lp.AddCValueOp("delta2", "delta2", "p2"))
        instrs.append(lp.SendCMsgOp("delta2"))

        instrs.append(lp.ReturnResultOp("p1"))
        instrs.append(lp.ReturnResultOp("p2"))

        self.instructions = instrs
        self.subroutines = subroutines


class ServerProgram(lp.LirProgram):
    PEER = "client"

    def __init__(self) -> None:
        super().__init__([], {})

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile(self, context: ProgramContext) -> None:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Create EPR Pair
        epr1 = epr_socket.recv_keep()[0]
        epr2 = epr_socket.recv_keep()[0]
        epr2.cphase(epr1)

        subrt1 = conn.compile()
        subroutines = {"subrt1": subrt1}

        instrs: List[lp.ClassicalLirOp] = []
        instrs.append(lp.RunSubroutineOp("subrt1"))

        instrs.append(lp.ReceiveCMsgOp("delta1"))

        epr2.rot_Z(n=Template("delta1"), d=4)
        epr2.H()
        m1 = epr2.measure(store_array=False)

        subrt2 = conn.compile()
        subroutines["subrt2"] = subrt2

        instrs.append(lp.RunSubroutineOp("subrt2"))
        instrs.append(lp.AssignCValueOp("m1", m1))
        instrs.append(lp.SendCMsgOp("m1"))

        instrs.append(lp.ReceiveCMsgOp("delta2"))

        epr1.rot_Z(n=Template("delta2"), d=4)
        epr1.H()
        m2 = epr1.measure(store_array=False)
        subrt3 = conn.compile()
        subroutines["subrt3"] = subrt3

        instrs.append(lp.RunSubroutineOp("subrt3"))
        instrs.append(lp.AssignCValueOp("m2", m2))
        instrs.append(lp.ReturnResultOp("m1"))
        instrs.append(lp.ReturnResultOp("m2"))

        self.instructions = instrs
        self.subroutines = subroutines


PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=False,
        dummy=-1,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
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


def trap_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
    dummy: int = 1,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=True,
        dummy=dummy,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
    )
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    p1s = [result["p1"] for result in client_results]
    p2s = [result["p2"] for result in client_results]
    m1s = [result["m1"] for result in server_results]
    m2s = [result["m2"] for result in server_results]

    assert dummy in [1, 2]
    if dummy == 1:
        num_fails = len([(p, m) for (p, m) in zip(p1s, m2s) if p != m])
    else:
        num_fails = len([(p, m) for (p, m) in zip(p2s, m1s) if p != m])

    frac_fail = round(num_fails / num_times, 2)
    print(f"fail rate: {frac_fail}")


if __name__ == "__main__":
    num_times = 1

    sender_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    receiver_stack = StackConfig(
        name="server",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    # computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
    trap_round(cfg, num_times, dummy=1)
