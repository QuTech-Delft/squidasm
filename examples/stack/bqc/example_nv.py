from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import NVQDeviceConfig, StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
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

        p1: Future
        p2: Future
        outcomes = conn.new_array(length=2)

        def post_create(_: BaseNetQASMConnection, q: Qubit, index: RegFuture):
            q.measure(future=outcomes.get_future_index(index))

        epr_socket.create_keep(2, sequential=True, post_routine=post_create)

        yield from conn.flush()

        p1 = int(outcomes.get_future_index(1))
        p2 = int(outcomes.get_future_index(0))

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

        # Create EPR Pair
        epr1, epr2 = epr_socket.recv_keep(2)

        m1 = epr2.measure(store_array=False)
        m2 = epr1.measure(store_array=False)
        yield from conn.flush()

        m1 = int(m1)
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

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    p1s = [result["p1"] for result in client_results]
    p2s = [result["p2"] for result in client_results]

    m1s = [result["m1"] for result in server_results]
    m2s = [result["m2"] for result in server_results]

    print(f"p1s: {''.join(str(x) for x in p1s)}")
    print(f"m1s: {''.join(str(x) for x in m1s)}")
    epr1_errors = sum(i != j for i, j in zip(p1s, m1s))
    print(f"epr1 errors: {epr1_errors}")

    print(f"p2s: {''.join(str(x) for x in p2s)}")
    print(f"m2s: {''.join(str(x) for x in m2s)}")

    epr2_errors = sum(i != j for i, j in zip(p2s, m2s))
    print(f"epr2 errors: {epr2_errors}")


if __name__ == "__main__":
    num_times = 100
    LogManager.set_log_level("WARNING")

    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config_nv.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)
    cfg.stacks[0].qdevice_cfg = NVQDeviceConfig.perfect_config()
    cfg.stacks[1].qdevice_cfg = NVQDeviceConfig.perfect_config()

    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
