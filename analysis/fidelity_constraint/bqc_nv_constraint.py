from __future__ import annotations

import datetime
import json
import math
import os
import random
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import matplotlib.pyplot as plt
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
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class CompileVersion(Enum):
    NETQASM_RETRY = 0
    HOST_RETRY = 1
    NO_RETRY = 2


COMPILE_VERSIONS = ["nqasm_retry", "host_retry"]
FORMATS = {
    "nqasm_retry": "-ro",
    "host_retry": "-bs",
    "no_retry": "-gs",
}
FORMATS_2 = {
    "nqasm_retry": "--ro",
    "host_retry": "--bo",
    "no_retry": "--go",
}
VERSION_LABELS = {
    "nqasm_retry": "NetQASM retry",
    "host_retry": "Host retry",
    "no_retry": "No retry",
}

X_LABELS = {
    "host_qnos_latency_duration": "Host <-> QNodeOS latency (ms)",
    "host_qnos_latency_error_rate": "Host <-> QNodeOS latency (ms)",
}

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
        compile_version: CompileVersion = CompileVersion.NO_RETRY,
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2
        self._compile_version = compile_version

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
                "compile_version": self._compile_version,
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

        GlobalSimData.reset_custom_event_count("EPR attempt")

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

        if self._compile_version == CompileVersion.NETQASM_RETRY:
            epr_socket.create_keep(
                2,
                sequential=True,
                post_routine=post_create,
                min_fidelity_all_at_end=90,
                max_tries=MAX_TRIES,
            )
            yield from conn.flush()
        elif self._compile_version == CompileVersion.HOST_RETRY:
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

        else:
            epr_socket.create_keep(2, sequential=True, post_routine=post_create)
            yield from conn.flush()

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

        attempt_count = GlobalSimData.get_custom_event_count("EPR attempt")
        print(f"attempt count: {attempt_count}")

        return {"p1": p1, "p2": p2, "attempts": attempt_count}


class ServerProgram(Program):
    PEER = "client"

    def __init__(
        self, compile_version: CompileVersion = CompileVersion.NO_RETRY
    ) -> None:
        self._compile_version = compile_version

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={"compile_version": self._compile_version},
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

        start = ns.sim_time()

        if self._compile_version == CompileVersion.NETQASM_RETRY:
            epr1, epr2 = epr_socket.recv_keep(
                2,
                min_fidelity_all_at_end=90,
                max_tries=MAX_TRIES,
            )
            epr2.cphase(epr1)

            yield from conn.flush()
        elif self._compile_version == CompileVersion.HOST_RETRY:
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
        else:
            epr1, epr2 = epr_socket.recv_keep(2)
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

        end = ns.sim_time()
        return {"m1": m1, "m2": m2, "duration": (end - start)}


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
    compile_version: CompileVersion = CompileVersion.NO_RETRY,
    use_random_inputs: bool = False,
) -> SimulationOutput:
    if use_random_inputs:
        alpha = random.uniform(-PI, PI)
        beta = random.uniform(-PI, PI)
        theta1 = random.uniform(-PI, PI)
        theta2 = random.uniform(-PI, PI)
        dummy = random.randrange(1, 3)

    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=True,
        dummy=dummy,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
        compile_version=compile_version,
    )
    server_program = ServerProgram(compile_version=compile_version)

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
    # print(f"fail rate: {frac_fail}")
    succ_rate_metric = SuccessRate(
        "success", num_succ=(num_times - num_fails), num_times=num_times
    )

    durations = [result["duration"] for result in server_results]
    duration_metric = Metric("duration", durations)

    attempts = [result["attempts"] for result in client_results]
    attempt_count_metric = Metric("attempt_count", attempts)

    return SimulationOutput(
        # error_rate=frac_fail,
        succ_rate=succ_rate_metric,
        duration=duration_metric,
        attempt_count=attempt_count_metric,
    )


class SuccessRate:
    def __init__(self, name: str, num_succ: int, num_times: int) -> None:
        self._name = name
        self._num_succ = num_succ
        self._num_times = num_times

    @property
    def success_rate(self) -> float:
        return self._num_succ / self._num_times

    @property
    def fail_rate(self) -> float:
        return 1 - self.success_rate

    @property
    def confidence_interval_95(self) -> float:
        p = self.success_rate
        n = self._num_times
        return 1.96 * math.sqrt(p * (1 - p) / n)

    def serialize(self) -> Dict:
        return {
            "success_rate": self.success_rate,
            "conf_95": self.confidence_interval_95,
        }


class Metric:
    def __init__(self, name: str, data: List[Any]) -> None:
        self._name = name
        self._data = data

        self._mean: Optional[float] = None
        self._std_error: Optional[float] = None

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def data(self) -> List[Any]:
        return self._data

    @property
    def mean(self) -> float:
        if self._mean is None:
            self._mean = sum(self._data) / self.size
        return self._mean

    @property
    def std_error(self) -> float:
        if self._std_error is None:
            variance = (
                sum((d - self.mean) * (d - self.mean) for d in self.data) / self.size
            )
            self._std_error = math.sqrt(variance) / math.sqrt(self.size)
        return self._std_error

    def serialize(self) -> Dict:
        return {"mean": self.mean, "std_error": self.std_error}


@dataclass
class SimulationInput:
    fidelity: float
    prob_success: float
    host_qnos_latency: float
    t2_time: float
    compile_version: CompileVersion


@dataclass
class SimulationMeta:
    num_times: int
    sweep_variable: str
    metrics: List[str]


@dataclass
class SimulationOutput:
    succ_rate: SuccessRate
    duration: Metric
    attempt_count: Metric

    def serialize(self) -> Dict:
        return {
            "succ_rate": self.succ_rate.serialize(),
            "duration": self.duration.serialize(),
            "attempt_coutn": self.attempt_count.serialize(),
        }


def simulate(
    input: SimulationInput, meta: SimulationMeta
) -> Dict[float, SimulationOutput]:
    start = ns.sim_time()

    GlobalSimData.create_custom_event_type("EPR attempt")

    results: Dict[float, SimulationOutput] = {}

    # for latency in range(int(1e6), int(10e6), int(4e6)):
    for latency in range(int(1e6), int(10e6), int(1e6)):

        cfg.links[0].cfg["fidelity"] = input.fidelity
        cfg.links[0].cfg["prob_success"] = input.prob_success
        cfg.stacks[0].host_qnos_latency = latency
        cfg.stacks[1].host_qnos_latency = latency
        cfg.stacks[0].qdevice_cfg.electron_T2 = input.t2_time
        cfg.stacks[0].qdevice_cfg.carbon_T2 = input.t2_time
        cfg.stacks[1].qdevice_cfg.electron_T2 = input.t2_time
        cfg.stacks[1].qdevice_cfg.carbon_T2 = input.t2_time

        output = trap_round(
            cfg=cfg,
            num_times=meta.num_times,
            compile_version=input.compile_version,
            use_random_inputs=True,
        )
        results[latency] = output

        print(f"simulated time: {ns.sim_time() - start}")

        # print(output)
        dur_mean = round(output.duration.mean, 3)
        dur_err = round(output.duration.std_error, 3)
        att_mean = round(output.attempt_count.mean, 3)
        att_err = round(output.attempt_count.std_error, 3)

        print("RESULTS\n")
        print(f"error rate  : {1 - output.succ_rate.success_rate}")
        print(f"duration    : {dur_mean} (+/- {dur_err})")
        print(f"num attempts: {att_mean} (+/- {att_err})")

    GlobalSimData.remove_custom_event_type("EPR attempt")

    return results


def create_png(param_name):
    output_dir = os.path.join(os.path.dirname(__file__), "plots")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"bqc_sweep_{param_name}_{timestamp}.png")
    plt.savefig(output_path)
    print(f"plot written to {output_path}")


def plot_host_qnos_latency_duration(
    data_nqasm_retry: Dict[float, SimulationOutput],
    data_host_retry: Dict[float, SimulationOutput],
    data_no_retry: Dict[float, SimulationOutput],
):
    param_name = "host_qnos_latency_duration"
    fig, ax = plt.subplots()
    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Duration")

    for compile_type in ["nqasm_retry", "host_retry", "no_retry"]:
        if compile_type == "nqasm_retry":
            data = data_nqasm_retry
        elif compile_type == "host_retry":
            data = data_host_retry
        else:
            data = data_no_retry

        sweep_values = [v / 1e6 for v in data.keys()]
        means = [v.duration.mean for v in data.values()]
        std_errs = [v.duration.std_error for v in data.values()]
        ax.errorbar(
            x=sweep_values,
            y=means,
            yerr=std_errs,
            fmt=FORMATS[compile_type],
            label=VERSION_LABELS[compile_type],
        )

    ax.set_title("Duration", wrap=True)
    ax.legend()
    create_png(param_name)


def plot_host_qnos_latency_error_rate(
    data_nqasm_retry: Dict[float, SimulationOutput],
    data_host_retry: Dict[float, SimulationOutput],
    data_no_retry: Dict[float, SimulationOutput],
):
    param_name = "host_qnos_latency_error_rate"
    fig, ax = plt.subplots()
    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")

    # for compile_type in ["nqasm_retry", "host_retry", "no_retry"]:
    for compile_type in ["nqasm_retry", "no_retry"]:
        if compile_type == "nqasm_retry":
            data = data_nqasm_retry
        elif compile_type == "host_retry":
            data = data_host_retry
        else:
            data = data_no_retry

        sweep_values = [v / 1e6 for v in data.keys()]
        error_rates = [(1 - v.succ_rate.success_rate) for v in data.values()]
        std_errs = [v.succ_rate.confidence_interval_95 for v in data.values()]
        ax.errorbar(
            x=sweep_values,
            y=error_rates,
            yerr=std_errs,
            fmt=FORMATS[compile_type],
            label=VERSION_LABELS[compile_type],
        )

    ax.set_title("Error rate", wrap=True)
    ax.legend()
    create_png(param_name)


def dump_data(data: Any, param_name: str) -> None:
    output_dir = os.path.join(os.path.dirname(__file__), "sweep_data_bqc")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(output_dir, f"{param_name}_{timestamp}.json"), "w") as f:
        json.dump(data, f)


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

    dump_file = os.path.join(os.path.dirname(__file__), "dump_bqc_nv_constraint.log")
    LogManager.log_to_file(dump_file)
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config_nv.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)
    cfg.stacks[0].qdevice_cfg = NVQDeviceConfig.perfect_config()
    cfg.stacks[1].qdevice_cfg = NVQDeviceConfig.perfect_config()

    input = SimulationInput(
        fidelity=0.9,
        prob_success=0.9,
        host_qnos_latency=10e6,
        t2_time=1e8,
        compile_version=CompileVersion.HOST_RETRY,
    )

    # cfg.links[0].cfg["fidelity"] = 0.9
    # # cfg.links[0].cfg["prob_success"] = 50.0e-5
    # cfg.links[0].cfg["prob_success"] = 1
    # # cfg.links[0].cfg["t_cycle"] = 50000
    # GlobalSimData.create_custom_event_type("EPR attempt")
    # result = trap_round(cfg, num_times=50, compile_version=CompileVersion.NETQASM_RETRY)
    # print(f"error rate: {1 - result.succ_rate.success_rate}")

    # exit()

    meta = SimulationMeta(
        num_times=500, sweep_variable="host_qnos_latency", metrics=["duration"]
    )

    # results_host = simulate(input, meta)
    input.compile_version = CompileVersion.NETQASM_RETRY
    results_nqasm = simulate(input, meta)

    input.compile_version = CompileVersion.NO_RETRY
    input.fidelity = 0.9
    input.prob_success = 1
    results_no_retry = simulate(input, meta)

    raw_data = {
        "nqasm_retry": {f: r.serialize() for f, r in results_nqasm.items()},
        # "host_retry": {f: r.serialize() for f, r in results_host.items()},
        "no_retry": {f: r.serialize() for f, r in results_no_retry.items()},
    }

    dump_data(raw_data, "host_qnos_latency")

    # plot_host_qnos_latency_duration(results_nqasm, results_host, results_no_retry)
    # plot_host_qnos_latency_error_rate(results_nqasm, results_host, results_no_retry)

    plot_host_qnos_latency_error_rate(results_nqasm, None, results_no_retry)
