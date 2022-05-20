import os
from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import NVQDeviceConfig, StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_program",
            parameters={},
            csockets=[],
            epr_sockets=[],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        q = Qubit(context.connection)
        yield from context.connection.flush()


def test_local():
    LogManager.set_log_level("DEBUG")

    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    instr_latency = 2e3
    host_qnos_latency = 1e6
    init_time = NVQDeviceConfig.perfect_config().electron_init

    cfg.stacks[0].instr_latency = instr_latency
    cfg.stacks[0].host_qnos_latency = host_qnos_latency

    alice_program = AliceProgram()

    run(cfg, {"client": alice_program})

    end_time = ns.sim_time()

    expected_time = (
        3 * instr_latency  # 3 instructions
        + 1 * init_time  # one of which is an 'init'
        + 2 * host_qnos_latency  # InitNewApp + response
        + 2 * host_qnos_latency  # Subroutine + response
        + 1 * host_qnos_latency  # StopApp
    )

    assert end_time == expected_time


if __name__ == "__main__":
    test_local()
