import os
from typing import Any, Dict, Generator

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

# Example of two nodes creating and directly measuring EPR pairs.


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        results = epr_socket.create_measure(number=self._num_pairs)

        yield from conn.flush()

        outcomes = [int(r.measurement_outcome) for r in results]

        return outcomes


class ServerProgram(Program):
    PEER = "client"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        results = epr_socket.recv_measure(number=self._num_pairs)

        yield from conn.flush()

        outcomes = [int(r.measurement_outcome) for r in results]

        return outcomes


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

    num_times = 1
    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    num_pairs = 10

    client_program = ClientProgram(basis="Z", num_pairs=num_pairs)
    server_program = ServerProgram(basis="Z", num_pairs=num_pairs)

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    for i, (client_result, server_result) in enumerate(
        zip(client_results, server_results)
    ):
        print(f"run {i}:")
        client_outcomes = [r for r in client_result]
        server_outcomes = [r for r in server_result]
        print(f"client: {client_outcomes}")
        print(f"server: {server_outcomes}")
