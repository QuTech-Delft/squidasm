from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Tuple

from netqasm.lang.parsing.text import parse_text_presubroutine
from profiling import profile

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

PRECOMPILE = False
RANDOMIZE_ANGLE = False


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

        start = time.time() * 1e6
        process_start = time.process_time() * 1e6

        p1 = int(p1)

        delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi

        end = time.time() * 1e6
        process_end = time.process_time() * 1e6

        duration = end - start
        process_duration = process_end - process_start

        csocket.send_float(delta1)

        return {"p1": p1, "duration": duration, "process_duration": process_duration}


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
        if RANDOMIZE_ANGLE:
            delta1 = random.choice([0, PI_OVER_2, PI, -PI_OVER_2])
        start = time.time() * 1e6
        process_start = time.process_time() * 1e6

        if PRECOMPILE:
            SERVER_SUBRT.app_id = conn.app_id
            # print(SERVER_SUBRT.commands[1].operands)
            SERVER_SUBRT.commands[1].operands[1] = 3
            SERVER_SUBRT.commands[1].operands[2] = 1
            end = time.time() * 1e6
            process_end = time.process_time() * 1e6
            yield from conn.commit_subroutine(SERVER_SUBRT)
            m2 = conn.shared_memory.get_register("M0")
        else:
            epr.rot_Z(angle=delta1)
            epr.H()
            m2 = epr.measure(store_array=False)

            # end = time.time() * 1e6
            # process_end = time.process_time() * 1e6
            # yield from conn.flush()

            subroutine = conn._builder._pop_pending_subroutine()
            end = time.time() * 1e6
            process_end = time.process_time() * 1e6
            yield from conn.commit_subroutine(subroutine)
            m2 = int(m2)

        duration = end - start
        process_duration = process_end - process_start

        return {"m2": m2, "duration": duration, "process_duration": process_duration}


@dataclass
class Statistics:
    name: str
    mean: float
    std_error: float
    min_value: float
    max_value: float

    def to_string(self):
        return f"[{self.name}] {self.mean}, {self.std_error} (max: {self.max_value}, min: {self.min_value})"


def compute_statistics(name: str, items: List[Any]) -> Statistics:
    length = len(items)
    mean = round(sum(items) / length, 3)
    variance = sum((d - mean) * (d - mean) for d in items) / length
    std_deviation = math.sqrt(variance)
    std_error = round(std_deviation / math.sqrt(length), 3)
    min_value = min(items)
    max_value = max(items)
    return Statistics(name, mean, std_error, min_value, max_value)


def get_distribution(
    cfg: StackNetworkConfig,
    num_times: int,
    alpha: float,
    theta1: float,
    r1: int = 0,
) -> None:
    client_program = ClientProgram(alpha=alpha, theta1=theta1, r1=r1)
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    durations = [result["duration"] for result in server_results]
    process_durations = [result["process_duration"] for result in server_results]
    # print(durations)
    m2s = [result["m2"] for result in server_results]

    client_durations = [result["duration"] for result in client_results]
    client_process_durations = [result["process_duration"] for result in client_results]

    print("\nserver:")
    print(compute_statistics("durations", durations).to_string())
    print(compute_statistics("process_durations", process_durations).to_string())
    # print(compute_statistics("m2", m2s).to_string())

    print("\nclient:")
    print(compute_statistics("client_durations", client_durations).to_string())
    print(
        compute_statistics(
            "client_process_durations", client_process_durations
        ).to_string()
    )
    print(client_durations)


PI = math.pi
PI_OVER_2 = math.pi / 2


# @profile(sort_by="cumulative", lines_to_print=1000, strip_dirs=True)
def main():
    num_times = 1000

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
    RANDOMIZE_ANGLE = True

    print("NO PRECOMPILE:")
    PRECOMPILE = False
    main()

    print("\nPRECOMPILE:")
    PRECOMPILE = True
    main()
