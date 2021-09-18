from __future__ import annotations

import math
from typing import Any, Dict, Generator, List, Tuple

from run import LinkType, run_stacks, setup_stacks

from pydynaa import EventExpression
from squidasm.run.stack.config import NVQDeviceConfig, perfect_nv_config
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


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

        epr = epr_socket.create()[0]

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

        epr = epr_socket.recv()[0]
        yield from conn.flush()

        delta1 = yield from csocket.recv_float()

        epr.rot_Z(angle=delta1)
        epr.H()
        m2 = epr.measure(store_array=False)

        yield from conn.flush()
        m2 = int(m2)

        return {"m2": m2}


def run(
    alpha: float,
    theta1: float,
    nv_config: NVQDeviceConfig,
    link_type: LinkType,
    r1: int = 0,
    num: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    client, server, link = setup_stacks(nv_config, link_type)

    client.host.enqueue_program(
        program=ClientProgram(
            alpha=alpha,
            theta1=theta1,
            r1=r1,
        ),
        num_times=num,
    )
    server.host.enqueue_program(program=ServerProgram(), num_times=num)

    client_results, server_results = run_stacks(client, server, link)
    return client_results, server_results


def get_distribution(
    alpha: float,
    theta1: float,
    nv_config: NVQDeviceConfig,
    link_type: LinkType,
    num: int,
) -> None:
    _, server_results = run(alpha, theta1, nv_config, link_type, num=num)
    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


PI = math.pi
PI_OVER_2 = math.pi / 2

if __name__ == "__main__":
    num = 100

    cfg = perfect_nv_config()
    link = LinkType.PERFECT
    get_distribution(0, 0, cfg, link, num)
    get_distribution(math.pi, 0, cfg, link, num)
    get_distribution(math.pi / 2, 0, cfg, link, num)

    cfg = perfect_nv_config()
    link = LinkType.NV
    get_distribution(0, 0, cfg, link, num)
    get_distribution(math.pi, 0, cfg, link, num)
    get_distribution(math.pi / 2, 0, cfg, link, num)

    cfg = NVQDeviceConfig()
    link = LinkType.NV
    get_distribution(0, 0, cfg, link, num)
    get_distribution(math.pi, 0, cfg, link, num)
    get_distribution(math.pi / 2, 0, cfg, link, num)
