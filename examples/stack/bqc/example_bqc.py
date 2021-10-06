from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator

from netqasm.lang.ir import BreakpointAction

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
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

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Create EPR pair
        epr1 = epr_socket.create()[0]

        # RSP
        if self._trap and self._dummy == 2:
            # remotely-prepare a dummy state
            p2 = epr1.measure(store_array=False)
        else:
            epr1.rot_Z(angle=self._theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)

        # Create EPR pair
        epr2 = epr_socket.create()[0]

        # RSP
        if self._trap and self._dummy == 1:
            # remotely-prepare a dummy state
            p1 = epr2.measure(store_array=False)
        else:
            epr2.rot_Z(angle=self._theta1)
            epr2.H()
            p1 = epr2.measure(store_array=False)

        yield from conn.flush()

        p1 = int(p1)
        p2 = int(p2)

        if self._trap and self._dummy == 2:
            delta1 = -self._theta1 + (p1 + self._r1) * math.pi
        else:
            delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi
        csocket.send_float(delta1)

        m1 = yield from csocket.recv_int()
        if self._trap and self._dummy == 1:
            delta2 = -self._theta2 + (p2 + self._r2) * math.pi
        else:
            delta2 = (
                math.pow(-1, (m1 + self._r1)) * self._beta
                - self._theta2
                + (p2 + self._r2) * math.pi
            )
        csocket.send_float(delta2)

        return {"p1": p1, "p2": p2}


class ServerProgram(Program):
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Create EPR Pair
        epr1 = epr_socket.recv()[0]
        epr2 = epr_socket.recv()[0]
        epr2.cphase(epr1)

        yield from conn.flush()

        delta1 = yield from csocket.recv_float()

        epr2.rot_Z(angle=delta1)
        epr2.H()
        m1 = epr2.measure(store_array=False)
        yield from conn.flush()

        m1 = int(m1)

        csocket.send_int(m1)

        delta2 = yield from csocket.recv_float()

        epr1.rot_Z(angle=delta2)
        epr1.H()
        conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)
        m2 = epr1.measure(store_array=False)
        yield from conn.flush()

        m2 = int(m2)
        return {"m1": m1, "m2": m2}


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
    LogManager.set_log_level("WARNING")
    # ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)

    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
    trap_round(cfg, num_times, dummy=1)
