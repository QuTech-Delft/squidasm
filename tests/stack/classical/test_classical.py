import os
from typing import Any, Dict, Generator

import netsquid as ns

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]
        csocket.send("hello")
        response = yield from csocket.recv()
        print(f"received response: {response}")
        yield from context.connection.flush()

        return {"response": response}


class ServerProgram(Program):
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]
        msg = yield from csocket.recv()
        print(f"received message: {msg}")
        csocket.send("hello back")
        yield from context.connection.flush()

        return {"msg": msg}


def test_classical_messaging():
    LogManager.set_log_level("WARNING")

    num_times = 1
    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    host_host_latency = 2e5
    cfg.links[0].host_host_latency = host_host_latency

    client_program = ClientProgram()
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    end_time = ns.sim_time()

    # Verify program results.
    assert server_results[0]["msg"] == "hello"
    assert client_results[0]["response"] == "hello back"

    # Verify that exactly two messages were sent from host to host,
    # and that nothing else happened that took simulated time.
    assert end_time == 2 * host_host_latency


if __name__ == "__main__":
    test_classical_messaging()
