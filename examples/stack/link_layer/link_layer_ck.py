import logging
from typing import Any, Dict, Generator, List, Tuple

import yaml
from netqasm.logging.glob import get_netqasm_logger, set_log_level
from netqasm.sdk.epr_socket import EPRType

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    LinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
    perfect_nv_config,
)
from squidasm.run.stack.run import run
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
    set_log_level("WARNING")
    fileHandler = logging.FileHandler("{0}/{1}.log".format(".", "debug"), mode="w")
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    fileHandler.setFormatter(formatter)
    get_netqasm_logger().addHandler(fileHandler)

    num_times = 3

    cfg = StackNetworkConfig.from_file("config.yaml")

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
