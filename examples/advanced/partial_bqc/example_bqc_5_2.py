from __future__ import annotations

from typing import Any, Dict, Generator

from netqasm.sdk.qubit import Qubit
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.base_configs import (
    CLinkConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from netsquid_netbuilder.modules.clinks.instant import InstantCLinkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig

from pydynaa import EventExpression
from squidasm.run.stack.run import run
from netsquid_driver.classical_socket_service import ClassicalSocket
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
        stack1="client", stack2="server", typ="perfect", cfg=PerfectLinkConfig()
    )

    clink = CLinkConfig(
        stack1="client", stack2="server", typ="instant", cfg=InstantCLinkConfig()
    )

    cfg = StackNetworkConfig(
        stacks=[client_stack, server_stack], links=[link], clinks=[clink]
    )

    client_program = ClientProgram(alpha=0, beta=0)
    server_program = ServerProgram()

    results = run(cfg, {"client": client_program, "server": server_program})
    print(results)