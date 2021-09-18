from __future__ import annotations

import math
from typing import Any, Dict, Generator, List, Tuple

from netqasm.lang.ir import BreakpointAction
from netqasm.logging.glob import set_log_level

from pydynaa import EventExpression
from squidasm.run import stack
from squidasm.run.stack import NVLinkConfig
from squidasm.sim.stack.config import (
    NVQDeviceConfig,
    perfect_generic_config,
    perfect_nv_config,
)
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


if __name__ == "__main__":
    num = 200
    set_log_level("DEBUG")

    client = stack.StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=perfect_nv_config(),
        # qdevice_typ="generic",
        # qdevice_cfg=perfect_generic_config(),
    )
    server = stack.StackConfig(
        name="server",
        # qdevice_typ="nv",
        # qdevice_cfg=perfect_nv_config(),
        qdevice_typ="generic",
        qdevice_cfg=perfect_generic_config(),
    )
    nv_link_config = NVLinkConfig(
        length_A=0.01, length_B=0.01, full_cycle=0.1, cycle_time=1.0, alpha=0.9
    )
    link = stack.LinkConfig(
        stack1="client",
        stack2="server",
        typ="nv",
        cfg=nv_link_config,
        # typ="perfect",
    )

    cfg = stack.StackNetworkConfig(stacks=[client, server], links=[link])

    client_program = ClientProgram(
        alpha=0, beta=0, trap=False, dummy=-1, theta1=0.0, theta2=0.0, r1=0, r2=0
    )
    server_program = ServerProgram()

    results = stack.run(cfg, {"client": client_program, "server": server_program})
    print(results)
