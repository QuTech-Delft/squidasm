from __future__ import annotations

import math
import os
from random import randint
from typing import Any, Dict, Generator

from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.sdk.connection import BaseNetQASMConnection
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
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.netstack import EprSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

M = 1
N = 1

NUM_QUBITS = 20


class CoinFlipProgram(Program):
    def send_qubit(
        self, q: Qubit, context: ProgramContext
    ) -> Generator[EventExpression, None, None]:
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]
        epr = epr_socket.create_keep(1)[0]
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()
        yield from context.connection.flush()
        csocket.send_int(int(m1))
        csocket.send_int(int(m2))

    def recv_qubit(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Qubit]:
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]
        epr = epr_socket.recv_keep(1)[0]
        yield from context.connection.flush()
        m1 = yield from csocket.recv_int()
        m2 = yield from csocket.recv_int()
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()
        return epr


class SenderProgram(CoinFlipProgram):
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
            max_qubits=NUM_QUBITS,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        a = [randint(0, 1) for _ in range(M)]
        c = [[randint(0, 1) for _ in range(M)] for _ in range(N)]

        rcvd_qubits = [[[None, None] for _ in range(M)] for _ in range(N)]
        returned_indices = [[None for _ in range(M)] for _ in range(N)]
        returned_qubits = [[None for _ in range(M)] for _ in range(N)]

        for i in range(N):
            for j in range(M):
                sent_q1 = Qubit(conn)
                sent_q2 = Qubit(conn)
                if c[i][j] == 1:
                    sent_q1.X()
                else:
                    sent_q2.X()
                yield from self.send_qubit(sent_q1, context)
                yield from self.send_qubit(sent_q2, context)

                rcvd_qubits[i][j][0] = yield from self.recv_qubit(context)
                rcvd_qubits[i][j][1] = yield from self.recv_qubit(context)

        for i in range(N):
            for j in range(M):
                e = a[j] ^ c[i][j]
                csocket.send_int(e)

                returned_qubits[i][j] = yield from self.recv_qubit(context)

                f = yield from csocket.recv_int()
                if f == 0:
                    # return 2nd particle
                    yield from self.send_qubit(rcvd_qubits[i][j][1], context)
                    returned_indices[i][j] = 1
                else:
                    # return 1st particle
                    yield from self.send_qubit(rcvd_qubits[i][j][0], context)
                    returned_indices[i][j] = 0

        for j in range(M):
            csocket.send_int(a[j])
            b = yield from csocket.recv_int()
            b_tilde = None
            for i in range(N):
                returned_index = returned_indices[i][j]
                q = rcvd_qubits[i][j][1 - returned_index]
                b_tilde = q.measure()
            yield from conn.flush()

        for j in range(M):
            a = None
            for i in range(N):
                returned_index = returned_indices[i][j]
                q = returned_qubits[i][j]
                a = q.measure()
            yield from conn.flush()

        yield from conn.flush()

        final_bit = int(a) ^ int(b_tilde)
        return {"final_bit": final_bit}


class ReceiverProgram(CoinFlipProgram):
    PEER = "sender"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="receiver_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=NUM_QUBITS,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        b = [randint(0, 1) for _ in range(N)]
        d = [[randint(0, 1) for _ in range(M)] for _ in range(N)]

        rcvd_qubits = [[[None, None] for _ in range(M)] for _ in range(N)]
        returned_indices = [[None for _ in range(M)] for _ in range(N)]
        returned_qubits = [[None for _ in range(M)] for _ in range(N)]

        for i in range(N):
            for j in range(M):
                rcvd_qubits[i][j][0] = yield from self.recv_qubit(context)
                rcvd_qubits[i][j][1] = yield from self.recv_qubit(context)

                sent_q1 = Qubit(conn)
                sent_q2 = Qubit(conn)
                if d[i][j] == 1:
                    sent_q1.X()
                else:
                    sent_q2.X()
                yield from self.send_qubit(sent_q1, context)
                yield from self.send_qubit(sent_q2, context)

        for i in range(N):
            for j in range(M):
                e = yield from csocket.recv_int()
                if e == 0:
                    # return 2nd particle
                    yield from self.send_qubit(rcvd_qubits[i][j][1], context)
                    returned_indices[i][j] = 1
                else:
                    # return 1st particle
                    yield from self.send_qubit(rcvd_qubits[i][j][0], context)
                    returned_indices[i][j] = 0
                f = b[j] ^ d[i][j]
                csocket.send_int(f)

                returned_qubits[i][j] = yield from self.recv_qubit(context)

        for j in range(M):
            a = yield from csocket.recv_int()
            csocket.send_int(b[j])
            a_tilde = None
            for i in range(N):
                returned_index = returned_indices[i][j]
                q = rcvd_qubits[i][j][1 - returned_index]
                a_tilde = q.measure()
            yield from conn.flush()

        for j in range(M):
            b = None
            for i in range(N):
                returned_index = returned_indices[i][j]
                q = returned_qubits[i][j]
                b = q.measure()
            yield from conn.flush()

        yield from conn.flush()

        final_bit = int(a_tilde) ^ int(b)
        return {"final_bit": final_bit}


if __name__ == "__main__":
    # LogManager.set_log_level("DEBUG")
    dump_file = os.path.join(os.path.dirname(__file__), "dump_coin_flipping.log")
    LogManager.log_to_file(dump_file)

    GlobalSimData.create_custom_event_type("EPR attempt")

    sender_stack = StackConfig(
        name="sender",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    sender_stack.qdevice_cfg.num_qubits = NUM_QUBITS
    sender_stack.qdevice_cfg.num_comm_qubits = NUM_QUBITS
    receiver_stack = StackConfig(
        name="receiver",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    receiver_stack.qdevice_cfg.num_qubits = NUM_QUBITS
    receiver_stack.qdevice_cfg.num_comm_qubits = NUM_QUBITS
    link = LinkConfig(
        stack1="sender",
        stack2="receiver",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    sender_program = SenderProgram(theta=math.pi, phi=0)
    receiver_program = ReceiverProgram()

    num_times = 20
    client_results, server_results = run(
        cfg,
        {"sender": sender_program, "receiver": receiver_program},
        num_times=num_times,
    )

    for cr, sr in zip(client_results, server_results):
        cbit = cr["final_bit"]
        sbit = sr["final_bit"]
        print(f"bits: {cbit}{sbit}")
