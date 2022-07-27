from __future__ import annotations

import math
import os
from typing import List

from netqasm.sdk.epr_socket import EPRSocket

from squidasm.qoala.lang import lhr as lp
from squidasm.qoala.runtime.config import (
    LinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.qoala.runtime.program import ProgramContext, ProgramInstance, SdkProgram
from squidasm.qoala.runtime.run import run
from squidasm.qoala.sim.common import LogManager
from squidasm.qoala.sim.netstack import EprSocket

PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
) -> None:
    # TODO: use alpha, beta to calculate delta1_discrete etc.

    client_lhr_file = os.path.join(os.path.dirname(__file__), "bqc_5_5_client.lhr")
    with open(client_lhr_file) as file:
        client_lhr_text = file.read()
    client_program = lp.LhrParser(client_lhr_text).parse()
    client_program.meta = lp.ProgramMeta(
        name="client_program",
        parameters=["alpha", "beta", "theta1", "r1"],
        csockets=["server"],
        epr_sockets=["server"],
        max_qubits=2,
    )

    server_lhr_file = os.path.join(os.path.dirname(__file__), "bqc_5_5_server.lhr")
    with open(server_lhr_file) as file:
        server_lhr_text = file.read()
    server_program = lp.LhrParser(server_lhr_text).parse()
    server_program.meta = lp.ProgramMeta(
        name="server_program",
        parameters={},
        csockets=["client"],
        epr_sockets=["client"],
        max_qubits=2,
    )

    client_instance = ProgramInstance(client_program, {"theta_discrete": 0}, 1, 0)
    server_instance = ProgramInstance(server_program, {}, 1, 0)

    _, server_results = run(
        cfg, {"client": client_instance, "server": server_instance}, num_times=num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


if __name__ == "__main__":
    num_times = 1

    LogManager.set_log_level("DEBUG")
    LogManager.log_to_file("dump.log")

    sender_stack = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    receiver_stack = StackConfig(
        name="server",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    cfg = StackNetworkConfig(stacks=[sender_stack, receiver_stack], links=[link])

    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
