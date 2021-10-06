import os
from typing import Any, Dict, Generator

from netqasm.sdk.epr_socket import EPRType

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={"basis": self._basis, "num_pairs": self._num_pairs},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        outcomes = conn.new_array(self._num_pairs)

        def post_create(conn, q, pair):
            array_entry = outcomes.get_future_index(pair)
            if self._basis == "X":
                q.H()
            elif self._basis == "Y":
                q.K()
            # store measurement outcome in array
            q.measure(array_entry)

        # Create EPR pair
        epr_socket.create(
            number=self._num_pairs,
            tp=EPRType.K,
            sequential=True,
            post_routine=post_create,
        )

        # Flush all pending commands
        yield from conn.flush()

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
            parameters={"basis": self._basis, "num_pairs": self._num_pairs},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        outcomes = conn.new_array(self._num_pairs)

        def post_create(conn, q, pair):
            array_entry = outcomes.get_future_index(pair)
            if self._basis == "X":
                q.H()
            elif self._basis == "Y":
                q.K()
            # store measurement outcome in array
            q.measure(array_entry)

        # Create EPR pair
        epr_socket.recv(
            number=self._num_pairs,
            tp=EPRType.K,
            sequential=True,
            post_routine=post_create,
        )

        # Flush all pending commands
        yield from conn.flush()

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
