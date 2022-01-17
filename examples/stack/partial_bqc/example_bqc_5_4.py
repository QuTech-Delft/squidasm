from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, Generator

from netqasm.lang.parsing.text import parse_text_presubroutine

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

server_subrt_path = os.path.join(os.path.dirname(__file__), "server_5_4.nqasm")
with open(server_subrt_path) as f:
    server_subrt_text = f.read()
SERVER_SUBRT = parse_text_presubroutine(server_subrt_text)

USE_CUSTOM_SUBROUTINES = False


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, alpha: float, theta1: float, r1: int):
        self._theta1 = theta1
        self._alpha = alpha
        self._r1 = r1

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={"theta1": self._theta1, "alpha": self._alpha, "r1": self._r1},
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

        epr = epr_socket.create_keep()[0]

        epr.rot_Z(angle=self._theta1)
        epr.H()

        p1 = epr.measure(store_array=False)

        yield from conn.flush()
        p1 = int(p1)

        delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi

        csocket.send_float(delta1)

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
        csocket: ClassicalSocket = context.csockets[self.PEER]

        epr = epr_socket.recv_keep()[0]
        yield from conn.flush()

        delta1 = yield from csocket.recv_float()
        start = time.time() * 1e6

        if USE_CUSTOM_SUBROUTINES:
            SERVER_SUBRT.app_id = conn.app_id
            # print(SERVER_SUBRT.commands[1].operands)
            SERVER_SUBRT.commands[1].operands[1] = 3
            SERVER_SUBRT.commands[1].operands[2] = 1
            # for i in range(int(1e4)):
            #     pass
            end = time.time() * 1e6
            yield from conn.commit_subroutine(SERVER_SUBRT)
            m2 = 0
        else:
            epr.rot_Z(angle=delta1)
            epr.H()
            m2 = epr.measure(store_array=False)

            # for i in range(int(1e4)):
            #     pass
            end = time.time() * 1e6

            yield from conn.flush()
            m2 = int(m2)

        duration = end - start

        return {"m2": m2, "duration": duration}


def get_distribution(
    cfg: StackNetworkConfig,
    num_times: int,
    alpha: float,
    theta1: float,
    r1: int = 0,
) -> None:
    client_program = ClientProgram(alpha=alpha, theta1=theta1, r1=r1)
    server_program = ServerProgram()

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    durations = [result["duration"] for result in server_results]
    # print(durations)

    mean = round(sum(durations) / len(durations), 3)
    variance = sum((d - mean) * (d - mean) for d in durations) / len(durations)
    std_deviation = math.sqrt(variance)
    std_error = round(std_deviation / math.sqrt(len(durations)), 3)

    max_dur = max(durations)
    min_dur = min(durations)

    print(f"{mean}, {std_error} (max: {max_dur}, min: {min_dur})")


PI = math.pi
PI_OVER_2 = math.pi / 2


def main():
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

    get_distribution(cfg, num_times, alpha=PI_OVER_2, theta1=-PI)


if __name__ == "__main__":
    USE_CUSTOM_SUBROUTINES = False
    main()
    USE_CUSTOM_SUBROUTINES = True
    main()
