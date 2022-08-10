from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator, List

import netsquid as ns
import numpy as np
from netqasm.lang.ir import BreakpointAction
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netsquid.qubits import qubitapi

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

PI = math.pi
PI_OVER_2 = math.pi / 2


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

        e = epr_socket.create_keep()[0]

        q = Qubit(conn)
        set_qubit_state(q, self._phi, self._theta)

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

        # Store the quantum state so we can later inspect it.
        conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)

        # Measure so quantum memory is available again for next round.
        e.measure()

        yield from conn.flush()

        # Return the state that was teleported.
        breakpoint = GlobalSimData.get_last_breakpoint_state()
        state = breakpoint["receiver"][0]
        return {"state": state}


def do_teleportation(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    phi: float = 0.0,
    theta: float = 0.0,
    verbose: bool = False,
) -> None:
    sender_program = SenderProgram(phi=phi, theta=theta)
    receiver_program = ReceiverProgram()

    sender_results, receiver_results = run(
        cfg,
        {"sender": sender_program, "receiver": receiver_program},
        num_times=num_times,
    )

    fidelities: List[float] = []
    for i in range(num_times):
        m1 = sender_results[i]["m1"]
        m2 = sender_results[i]["m2"]
        state = receiver_results[i]["state"]
        if verbose:
            print(
                f"\nresult {i}:\nm1 = {m1}, m2 = {m2}, state = \n{np.around(state, 4)}"
            )

        teleported = qubitapi.create_qubits(1)[0]
        qubitapi.assign_qstate(teleported, state)

        rotate_theta = ns.create_rotation_op(angle=theta, rotation_axis=(0, 1, 0))
        rotate_phi = ns.create_rotation_op(angle=phi, rotation_axis=(0, 0, 1))

        expected = qubitapi.create_qubits(1)[0]
        qubitapi.operate(expected, rotate_phi)
        qubitapi.operate(expected, rotate_theta)

        fid = qubitapi.fidelity(teleported, qubitapi.reduced_dm(expected), squared=True)
        if verbose:
            print(f"fidelity = {fid}")
        fidelities.append(fid)

    if verbose:
        print(f"\nall fidelities: {fidelities}")
    print(f"average fidelity: {round(sum(fidelities) / len(fidelities), 3)}")


if __name__ == "__main__":
    num_times = 20
    LogManager.set_log_level("WARNING")

    cwd = os.path.dirname(__file__)
    log_file = os.path.join(cwd, "qne_teleport.log")

    LogManager.log_to_file(log_file)
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(cwd, "config_nv.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)

    do_teleportation(cfg, num_times, phi=0, theta=0)
    do_teleportation(cfg, num_times, phi=PI, theta=0)
    do_teleportation(cfg, num_times, phi=0, theta=PI_OVER_2)
    # ...
