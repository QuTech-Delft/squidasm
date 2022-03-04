from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.lang.ir import BreakpointAction
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import NVQDeviceConfig, StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager, SubroutineAbortedError
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

MAX_TRIES = 1000
MAX_TRIES_ABORT = 1000


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
        use_fidelity_contraint: bool = False,
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2
        self._use_fidelity_constraint = use_fidelity_contraint

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
                "use_fidelity_constraint": self._use_fidelity_constraint,
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

        p1: Future
        p2: Future
        outcomes = conn.new_array(length=2)

        def post_create(_: BaseNetQASMConnection, q: Qubit, index: RegFuture):
            with index.if_eq(0):
                if not (self._trap and self._dummy == 2):
                    q.rot_Z(angle=self._theta2)
                    q.H()

            with index.if_eq(1):
                if not (self._trap and self._dummy == 1):
                    q.rot_Z(angle=self._theta1)
                    q.H()
            q.measure(future=outcomes.get_future_index(index))

        if self._use_fidelity_constraint:
            epr_socket.create_keep(
                2,
                sequential=True,
                post_routine=post_create,
                min_fidelity_all_at_end=80,
                max_tries=MAX_TRIES,
            )
            yield from conn.flush()
        else:
            max_tries = MAX_TRIES_ABORT
            for count in range(max_tries):
                try:
                    epr_socket.create_keep(
                        2, sequential=True, post_routine=post_create, max_time=10_000
                    )
                    yield from conn.flush()
                except SubroutineAbortedError:
                    if count == max_tries - 1:
                        raise RuntimeError(f"failed {max_tries} times, aborting.")
                    else:
                        conn.builder._reset()
                        conn.builder._mem_mgr.inactivate_qubits()
                        continue  # try again
                else:  # subroutine successfully executed
                    print(f"succeeded after {count + 1} times")
                    break

        p1 = int(outcomes.get_future_index(1))
        p2 = int(outcomes.get_future_index(0))

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

    def __init__(self, use_fidelity_contraint: bool = False) -> None:
        self._use_fidelity_constraint = use_fidelity_contraint

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={"use_fidelity_constraint": self._use_fidelity_constraint},
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

        if self._use_fidelity_constraint:
            epr1, epr2 = epr_socket.recv_keep(
                2,
                min_fidelity_all_at_end=80,
                max_tries=MAX_TRIES,
            )
            epr2.cphase(epr1)

            yield from conn.flush()
        else:
            max_tries = MAX_TRIES_ABORT
            for count in range(max_tries):
                try:
                    epr1, epr2 = epr_socket.recv_keep(2)
                    epr2.cphase(epr1)
                    yield from conn.flush()
                except SubroutineAbortedError:
                    if count == max_tries - 1:
                        raise RuntimeError(f"failed {max_tries} times, aborting.")
                    else:
                        conn.builder._reset()
                        conn.builder._mem_mgr.inactivate_qubits()
                        continue  # try again
                else:  # subroutine successfully executed
                    break

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

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


def trap_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
    dummy: int = 1,
    use_fidelity_constraint: bool = False,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=True,
        dummy=dummy,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
        use_fidelity_contraint=use_fidelity_constraint,
    )
    server_program = ServerProgram(use_fidelity_contraint=use_fidelity_constraint)

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
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

    frac_fail = round(num_fails / num_times, 2)
    print(f"fail rate: {frac_fail}")


if __name__ == "__main__":
    num_times = 100
    LogManager.set_log_level("WARNING")

    # num_times = 1
    # LogManager.set_log_level("DEBUG")

    dump_file = os.path.join(os.path.dirname(__file__), "dump_bqc_nv_constraint.log")
    LogManager.log_to_file(dump_file)
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config_nv.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)
    cfg.stacks[0].qdevice_cfg = NVQDeviceConfig.perfect_config()
    cfg.stacks[1].qdevice_cfg = NVQDeviceConfig.perfect_config()

    # computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)

    use_fidelity_constraint = False

    start = ns.sim_time()

    trap_round(
        cfg=cfg,
        num_times=num_times,
        dummy=2,
        use_fidelity_constraint=use_fidelity_constraint,
    )

    print(f"simulated time: {ns.sim_time() - start}")
