from __future__ import annotations

import math
from typing import Any, Dict, Generator, List, Tuple

from run import LinkType, run_stacks, setup_stacks

from pydynaa import EventExpression
from squidasm.netsquid.config import QDeviceConfig, perfect_nv_config
from squidasm.netsquid.csocket import ClassicalSocket
from squidasm.netsquid.program import Program, ProgramContext, ProgramMeta


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
        m2 = epr1.measure(store_array=False)
        yield from conn.flush()

        m2 = int(m2)
        return {"m1": m1, "m2": m2}


def run(
    alpha: float,
    beta: float,
    theta1: float,
    theta2: float,
    nv_config: QDeviceConfig,
    link_type: LinkType,
    trap: bool = False,
    dummy: int = -1,
    r1: int = 0,
    r2: int = 0,
    num: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    client, server, link = setup_stacks(nv_config, link_type)

    client.host.enqueue_program(
        program=ClientProgram(
            alpha=alpha,
            beta=beta,
            trap=trap,
            dummy=dummy,
            theta1=theta1,
            theta2=theta2,
            r1=r1,
            r2=r2,
        ),
        num_times=num,
    )
    server.host.enqueue_program(program=ServerProgram(), num_times=num)

    client_results, server_results = run_stacks(client, server, link)
    return client_results, server_results


PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    alpha: float,
    beta: float,
    theta1: float,
    theta2: float,
    nv_config: QDeviceConfig,
    link_type: LinkType,
    num: int,
) -> None:
    _, server_results = run(
        alpha=alpha,
        beta=beta,
        theta1=theta1,
        theta2=theta2,
        nv_config=nv_config,
        link_type=link_type,
        trap=False,
        dummy=-1,
        num=num,
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


def trap_round(
    alpha: float,
    beta: float,
    theta1: float,
    theta2: float,
    nv_config: QDeviceConfig,
    link_type: LinkType,
    dummy: int,
    num: int,
) -> None:
    client_results, server_results = run(
        alpha=alpha,
        beta=beta,
        theta1=theta1,
        theta2=theta2,
        nv_config=nv_config,
        link_type=link_type,
        trap=True,
        dummy=dummy,
        num=num,
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

    frac_fail = round(num_fails / num, 2)
    print(f"fail rate: {frac_fail}")


if __name__ == "__main__":
    num = 200

    cfg = perfect_nv_config()
    link = LinkType.PERFECT
    trap_round(0, 0, 0, 0, cfg, link, dummy=1, num=num)
    trap_round(0, 0, 0, 0, cfg, link, dummy=2, num=num)
    trap_round(PI, 0, 0, -PI_OVER_2, cfg, link, dummy=2, num=num)
    computation_round(PI_OVER_2, PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, PI_OVER_2, PI, cfg, link, num=num)

    cfg = perfect_nv_config()
    link = LinkType.NV
    trap_round(0, 0, 0, 0, cfg, link, dummy=1, num=num)
    trap_round(0, 0, 0, 0, cfg, link, dummy=2, num=num)
    trap_round(PI, 0, 0, -PI_OVER_2, cfg, link, dummy=2, num=num)
    computation_round(PI_OVER_2, PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, PI_OVER_2, PI, cfg, link, num=num)

    cfg = QDeviceConfig()
    link = LinkType.PERFECT
    trap_round(0, 0, 0, 0, cfg, link, dummy=1, num=num)
    trap_round(0, 0, 0, 0, cfg, link, dummy=2, num=num)
    trap_round(PI, 0, 0, -PI_OVER_2, cfg, link, dummy=2, num=num)
    computation_round(PI_OVER_2, PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, PI_OVER_2, PI, cfg, link, num=num)

    cfg = QDeviceConfig()
    link = LinkType.NV
    trap_round(0, 0, 0, 0, cfg, link, dummy=1, num=num)
    trap_round(0, 0, 0, 0, cfg, link, dummy=2, num=num)
    trap_round(PI, 0, 0, -PI_OVER_2, cfg, link, dummy=2, num=num)
    computation_round(PI_OVER_2, PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, 0, 0, cfg, link, num=num)
    computation_round(PI_OVER_2, -PI_OVER_2, PI_OVER_2, PI, cfg, link, num=num)
