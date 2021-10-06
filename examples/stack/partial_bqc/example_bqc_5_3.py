from __future__ import annotations

import math
from typing import Any, Dict, Generator

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, theta1: float) -> None:
        self._theta1 = theta1

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={"theta1": self._theta1},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        epr = epr_socket.create()[0]

        epr.rot_Z(angle=self._theta1)
        epr.H()

        p1 = epr.measure(store_array=False)
        yield from conn.flush()

        p1 = int(p1)
        return {"p1": p1}


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

        epr = epr_socket.recv()[0]

        epr.H()
        m2 = epr.measure(store_array=False)

        yield from conn.flush()

        m2 = int(m2)
        return {"m2": m2}


def get_distribution(cfg: StackNetworkConfig, num_times: int, theta1: float) -> None:
    client_program = ClientProgram(theta1=theta1)
    server_program = ServerProgram()

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"theta1: {theta1} -> dist (0, 1) = ({frac0}, {frac1})")


if __name__ == "__main__":
    num_times = 100

    client_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    server_stack = StackConfig(
        name="server",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])

    get_distribution(cfg, num_times, theta1=0)
    get_distribution(cfg, num_times, theta1=math.pi)
