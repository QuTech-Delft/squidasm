from typing import Any, Dict, Generator, List, Tuple

from apps.link_layer.link_layer import LinkLayerApplication
from netqasm.logging.glob import set_log_level
from netqasm.sdk.epr_socket import EPRType
from qnodeos.sdk.application import ApplicationContext
from run import LinkType, run_stacks, setup_stacks

from pydynaa import EventExpression
from squidasm.netsquid.config import QDeviceConfig, perfect_nv_config
from squidasm.netsquid.csocket import ClassicalSocket
from squidasm.netsquid.program import Program, ProgramContext, ProgramMeta


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
        csocket: ClassicalSocket = context.csockets[self.PEER]

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
        csocket: ClassicalSocket = context.csockets[self.PEER]

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


def run(
    basis: str,
    num_pairs: int,
    nv_config: QDeviceConfig,
    link_type: LinkType,
    num: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    client, server, link = setup_stacks(nv_config, link_type)

    client.host.enqueue_program(
        program=ClientProgram(basis=basis, num_pairs=num_pairs),
        num_times=num,
    )
    server.host.enqueue_program(
        program=ServerProgram(basis=basis, num_pairs=num_pairs), num_times=num
    )

    client_results, server_results = run_stacks(client, server, link)
    return client_results, server_results


if __name__ == "__main__":
    set_log_level("INFO")

    num = 1

    num_pairs = 2
    cfg = perfect_nv_config()
    link = LinkType.PERFECT
    client_results, server_results = run(
        basis="Z", num_pairs=num_pairs, nv_config=cfg, link_type=link, num=num
    )

    for i in range(num):
        client_outcomes = [r for r in client_results[i]]
        server_outcomes = [r for r in server_results[i]]
        print(client_outcomes)
        print(server_outcomes)
