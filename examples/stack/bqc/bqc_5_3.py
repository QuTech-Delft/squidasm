from __future__ import annotations

import math
from typing import Any, Dict, Generator, List

import netsquid as ns
from run import LinkType, run_stacks, setup_stacks

from pydynaa import EventExpression
from squidasm.sim.stack.config import NVQDeviceConfig, perfect_nv_config
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


def run(
    theta1: float, nv_config: NVQDeviceConfig, link_type: LinkType, num: int = 1
) -> List[Dict[str, Any]]:
    ns.sim_reset()
    client, server, link = setup_stacks(nv_config, link_type)

    client.host.enqueue_program(ClientProgram(theta1=theta1), num)
    server.host.enqueue_program(ServerProgram(), num)

    _, server_results = run_stacks(client, server, link)
    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    return num_zeros


def get_distribution(
    theta1: float, nv_config: NVQDeviceConfig, link_type: LinkType, num: int
) -> None:
    num_zeros = run(theta1, nv_config, link_type, num)
    frac0 = round(num_zeros / num, 2)
    frac1 = 1 - frac0
    print(f"theta1: {theta1} -> dist (0, 1) = ({frac0}, {frac1})")


if __name__ == "__main__":
    num = 100

    nv_config = perfect_nv_config()
    link_type = LinkType.PERFECT
    get_distribution(theta1=0, nv_config=nv_config, link_type=link_type, num=num)
    get_distribution(theta1=math.pi, nv_config=nv_config, link_type=link_type, num=num)

    nv_config = perfect_nv_config()
    link_type = LinkType.NV
    get_distribution(theta1=0, nv_config=nv_config, link_type=link_type, num=num)
    get_distribution(theta1=math.pi, nv_config=nv_config, link_type=link_type, num=num)

    nv_config = NVQDeviceConfig()  # default config
    link_type = LinkType.NV
    get_distribution(theta1=0, nv_config=nv_config, link_type=link_type, num=num)
    get_distribution(theta1=math.pi, nv_config=nv_config, link_type=link_type, num=num)
