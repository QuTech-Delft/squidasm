from __future__ import annotations

from typing import Any, Dict, Generator

from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, alpha: float, beta: float) -> None:
        self._alpha = alpha
        self._beta = beta

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={"alpha": self._alpha, "beta": self._beta},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket: ClassicalSocket = context.csockets[self.PEER]

        csocket.send_float(self._alpha)
        m1 = yield from csocket.recv_int()
        beta = -self._beta if m1 == 1 else self._beta
        csocket.send_float(beta)

        return {}


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
        csocket: ClassicalSocket = context.csockets[self.PEER]

        alpha = yield from csocket.recv_float()

        electron = Qubit(conn)
        carbon = Qubit(conn)

        carbon.H()
        electron.H()
        electron.cphase(carbon)

        electron.rot_Z(angle=alpha)
        electron.H()
        m1 = electron.measure(store_array=False)
        yield from conn.flush()
        m1 = int(m1)

        csocket.send_int(m1)

        beta = yield from csocket.recv_float()

        carbon.rot_Z(angle=beta)
        carbon.H()
        m2 = carbon.measure(store_array=False)

        yield from conn.flush()
        m2 = int(m2)

        return {"m1": m1, "m2": m2}


if __name__ == "__main__":
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

    client_program = ClientProgram(alpha=0, beta=0)
    server_program = ServerProgram()

    results = run(cfg, {"client": client_program, "server": server_program})
    print(results)
