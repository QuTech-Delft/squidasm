from __future__ import annotations

import math
from typing import Any, Dict, Generator

from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.logging.glob import set_log_level
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state

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

        e = epr_socket.create()[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.CREATE
        )
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

        e = epr_socket.recv()[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.RECEIVE
        )
        yield from conn.flush()

        m1 = yield from csocket.recv_int()
        m2 = yield from csocket.recv_int()

        if m2 == 1:
            e.X()
        if m1 == 1:
            e.Z()

        # conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)
        yield from conn.flush()


if __name__ == "__main__":
    set_log_level("INFO")

    sender_stack = StackConfig(
        name="sender",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    receiver_stack = StackConfig(
        name="receiver",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="sender",
        stack2="receiver",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    sender_program = SenderProgram(theta=math.pi, phi=0)
    receiver_program = ReceiverProgram()

    results = run(cfg, {"sender": sender_program, "receiver": receiver_program})
    print(results)
