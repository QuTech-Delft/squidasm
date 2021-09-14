from __future__ import annotations

from typing import Any, Dict, Generator, List

from netqasm.sdk.qubit import Qubit
from run import LinkType, run_stacks, setup_stacks

from pydynaa import EventExpression
from squidasm.sim.netsquid.config import perfect_nv_config
from squidasm.sim.netsquid.csocket import ClassicalSocket
from squidasm.sim.netsquid.program import Program, ProgramContext, ProgramMeta


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


def run(alpha: float, beta: float, num: int) -> List[Dict[str, Any]]:
    client, server, link = setup_stacks(perfect_nv_config(), LinkType.PERFECT)

    client.host.enqueue_program(ClientProgram(alpha=alpha, beta=beta), num)
    server.host.enqueue_program(ServerProgram(), num)

    _, server_results = run_stacks(client, server, link)
    return server_results


if __name__ == "__main__":
    results = run(alpha=0, beta=0, num=10)
    print(results)
