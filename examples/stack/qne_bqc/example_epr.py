from __future__ import annotations

import math
import os
from re import T
from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import Qubit
from netsquid.qubits import ketstates, qubitapi

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    LinkConfig,
    NVLinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

# BQC application run on NV hardware.


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

        epr = epr_socket.create_keep(1)[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, role=BreakpointRole.CREATE
        )
        m = epr.measure()
        yield from conn.flush()

        breakpoint = GlobalSimData.get_last_breakpoint_state()
        epr_state = breakpoint["client"][0]
        for i in range(4):
            for j in range(4):
                if abs(epr_state[i][j] < 1e-5):
                    epr_state[i][j] = 0
        print(epr_state)
        q0, q1 = qubitapi.create_qubits(2)
        qubitapi.assign_qstate([q0, q1], epr_state)
        fid = qubitapi.fidelity([q0, q1], ketstates.b00, squared=True)
        print(f"fidelity = {fid}")

        return {"m": int(m)}


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

        epr = epr_socket.recv_keep(1)[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, role=BreakpointRole.RECEIVE
        )
        m = epr.measure()
        yield from conn.flush()

        return {"m": int(m)}


PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=False,
        dummy=-1,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
    )
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    client = [r["m"] for r in client_results]
    server = [r["m"] for r in server_results]

    print("".join(str(c) for c in client))
    print("".join(str(s) for s in server))


if __name__ == "__main__":
    num_times = 1
    LogManager.set_log_level("WARNING")

    cwd = os.path.dirname(__file__)
    log_file = os.path.join(cwd, "qne_bqc.log")

    LogManager.log_to_file(log_file)
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    client_stack = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    server_stack = StackConfig(
        name="server",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        # stack1="client", stack2="server", typ="nv", cfg=NVLinkConfig.perfect_config()
        stack1="client",
        stack2="server",
        typ="nv",
        cfg=NVLinkConfig.perfect_config(),
    )
    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])

    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
