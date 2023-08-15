from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator

import netsquid as ns

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

# Example of using a `min_fidelity_all_at_end` constraint on the entangled pairs.


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
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        eprs = epr_socket.create_keep(
            number=2, min_fidelity_all_at_end=70, max_tries=20
        )

        m0 = eprs[0].measure()
        m1 = eprs[1].measure()

        yield from conn.flush()

        return {"m0": int(m0), "m1": int(m1)}


class ServerProgram(Program):
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        eprs = epr_socket.recv_keep(number=2, min_fidelity_all_at_end=70, max_tries=20)

        m0 = eprs[0].measure()
        m1 = eprs[1].measure()

        yield from conn.flush()

        return {"m0": int(m0), "m1": int(m1)}


PI = math.pi
PI_OVER_2 = math.pi / 2


def run_app(
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


if __name__ == "__main__":
    num_times = 1
    LogManager.set_log_level("WARNING")
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)

    run_app(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
