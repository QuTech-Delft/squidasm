from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator, List

import netsquid as ns
from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netsquid.qubits import ketstates, operators, qubit, qubitapi

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
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class SenderProgram(Program):
    PEER = "receiver"

    def __init__(
        self,
        theta: float,
        phi: float,
    ):
        self._theta = theta
        self._phi = phi

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="sender_program",
            parameters={
                "theta": self._theta,
                "phi": self._phi,
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

        q = Qubit(conn)
        set_qubit_state(q, self._phi, self._theta)

        e = epr_socket.create_keep()[0]
        q.cnot(e)
        q.H()
        m1 = q.measure()
        m2 = e.measure()

        yield from conn.flush()

        m1, m2 = int(m1), int(m2)

        csocket.send_int(m1)
        csocket.send_int(m2)

        return {"m1": m1, "m2": m2}


class ReceiverProgram(Program):
    PEER = "sender"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="receiver_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        e = epr_socket.recv_keep()[0]
        yield from conn.flush()

        m1 = yield from csocket.recv_int()
        m2 = yield from csocket.recv_int()

        if m2 == 1:
            e.X()
        if m1 == 1:
            e.Z()

        conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)
        e.measure()
        yield from conn.flush()

        all_states = GlobalSimData.get_last_breakpoint_state()
        state = all_states["receiver"][0]
        return state


def do_teleportation(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    theta: float = 0.0,
    phi: float = 0.0,
    log_level: str = "WARNING",
) -> List[float]:
    LogManager.set_log_level(log_level)

    sender_program = SenderProgram(theta=theta, phi=phi)
    receiver_program = ReceiverProgram()

    _, final_states = run(
        cfg,
        {"sender": sender_program, "receiver": receiver_program},
        num_times=num_times,
    )

    expected = qubitapi.create_qubits(1)[0]
    rot_theta = operators.create_rotation_op(theta, rotation_axis=(0, 1, 0))
    rot_phi = operators.create_rotation_op(phi, rotation_axis=(0, 0, 1))
    qubitapi.operate(expected, rot_theta)
    qubitapi.operate(expected, rot_phi)
    fidelities = [qubitapi.fidelity(expected, f, squared=True) for f in final_states]

    return fidelities


if __name__ == "__main__":
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    # link between sender and receiver
    link = cfg.links[0]

    link.cfg["fidelity"] = 0.8

    for _ in range(2):
        fidelities = do_teleportation(cfg, num_times=10, theta=0, phi=0)
        print(fidelities)
