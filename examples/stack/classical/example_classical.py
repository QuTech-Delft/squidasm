import os
from typing import Any, Dict, Generator

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


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

    num_times = 1
    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    client_program = ClientProgram()
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )
