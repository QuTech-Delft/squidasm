import os
from math import pi
from typing import Any, Dict, Generator

from netqasm.lang.parsing.text import parse_text_presubroutine
from netqasm.sdk import Qubit
from netqasm.sdk.epr_socket import EPRType
from netqasm.sdk.futures import Array

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    LinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

client_subrt_path = os.path.join(os.path.dirname(__file__), "client.nqasm")
with open(client_subrt_path) as f:
    client_subrt_text = f.read()
CLIENT_SUBRT = parse_text_presubroutine(client_subrt_text)

server_subrt_path = os.path.join(os.path.dirname(__file__), "server.nqasm")
with open(server_subrt_path) as f:
    server_subrt_text = f.read()
SERVER_SUBRT = parse_text_presubroutine(server_subrt_text)

MIN_FIDELITY_LIST = [60, 65]

USE_CUSTOM_SUBROUTINES = True


class FidelityVsRateProgram(Program):
    def __init__(self, num_repetitions: int):
        self._num_repetitions = num_repetitions
        self._bases = [
            "+X+X",
            "+Y+Y",
            "+Z+Z",
            "+X-X",
            "+Y-Y",
            "+Z-Z",
            "-X+X",
            "-Y+Y",
            "-Z+Z",
            "-X-X",
            "-Y-Y",
            "-Z-Z",
        ]

    @staticmethod
    def _to_key(fidelity: int, basis: str) -> str:
        return f"{str(fidelity)}-{basis}"

    def _create_outcomes_dict2(self, context: ProgramContext) -> Dict[str, Array]:
        outcomes = dict()
        array_len = len(MIN_FIDELITY_LIST) * len(self._bases) * self._num_repetitions
        array = context.connection.new_array(array_len)
        for i, fid in enumerate(MIN_FIDELITY_LIST):
            for j, basis in enumerate(self._bases):
                key = self._to_key(fidelity=fid, basis=basis)
                start = i * j * self._num_repetitions
                outcomes[key] = array.get_future_slice(
                    slice(start, start + self._num_repetitions)
                )
        return outcomes

    def _create_outcomes_dict(self, context: ProgramContext) -> Dict[str, Array]:
        outcomes = dict()
        for fid in MIN_FIDELITY_LIST:
            # for basis in self._bases:
            # key = self._to_key(fidelity=fid, basis=basis)
            # outcomes[key] = context.connection.new_array(self._num_repetitions)
            outcomes[fid] = context.connection.new_array(
                self._num_repetitions * len(self._bases)
            )
        return outcomes

    @staticmethod
    def _rotate_basis(qubit: Qubit, basis: str) -> None:
        if basis == "+X":
            qubit.rot_Y(angle=-pi / 2)
        elif basis == "+Y":
            qubit.rot_X(angle=pi / 2)
        elif basis == "-X":
            qubit.rot_Y(angle=pi / 2)
        elif basis == "-Y":
            qubit.rot_X(angle=-pi / 2)
        elif basis == "-Z":
            qubit.X()


class ClientProgram(FidelityVsRateProgram):
    PEER = "server"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={"num_repetitions": self._num_repetitions},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        if USE_CUSTOM_SUBROUTINES:
            yield from context.connection.commit_subroutine(CLIENT_SUBRT)
            return {
                "fidelity 60": context.connection.shared_memory.get_array(0),
                "fidelity 65": context.connection.shared_memory.get_array(1),
            }
        else:
            outcomes = self._create_outcomes_dict(context)

            with context.connection.loop(self._num_repetitions):
                for fid in MIN_FIDELITY_LIST:

                    def post_create(conn, q, pair):
                        # NOTE: the following is not possible at the moment:
                        # somehow use `pair` to decide basis
                        # somehow use loop index to calculate index in array
                        self._rotate_basis(q, basis="+X")
                        array_entry = outcomes[fid].get_future_index(pair)
                        q.measure(array_entry)

                    context.epr_sockets[self.PEER].create(
                        number=len(self._bases),
                        tp=EPRType.K,
                        sequential=True,
                        post_routine=post_create,
                    )
            yield from context.connection.flush()

            outcomes = {key: list(array) for key, array in outcomes.items()}
            return outcomes


class ServerProgram(FidelityVsRateProgram):
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={"num_repetitions": self._num_repetitions},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        if USE_CUSTOM_SUBROUTINES:
            yield from context.connection.commit_subroutine(SERVER_SUBRT)
            return {
                "fidelity 60": context.connection.shared_memory.get_array(0),
                "fidelity 65": context.connection.shared_memory.get_array(1),
            }
        else:
            outcomes = self._create_outcomes_dict(context)

            with context.connection.loop(self._num_repetitions):
                for fid in MIN_FIDELITY_LIST:

                    def post_create(conn, q, pair):
                        self._rotate_basis(q, basis="+X")
                        array_entry = outcomes[fid].get_future_index(pair)
                        q.measure(array_entry)

                    context.epr_sockets[self.PEER].recv(
                        number=len(self._bases),
                        tp=EPRType.K,
                        sequential=True,
                        post_routine=post_create,
                    )

            # Flush all pending commands
            yield from context.connection.flush()

            outcomes = {key: list(array) for key, array in outcomes.items()}
            return outcomes


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")
    # LogManager.log_to_file(os.path.join(os.path.dirname(__file__), "debug.log"))

    num_times = 1

    client = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    server = StackConfig(
        name="server",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(stack1=client.name, stack2=server.name, typ="perfect")

    cfg = StackNetworkConfig(stacks=[client, server], links=[link])

    client_program = ClientProgram(num_repetitions=2)
    server_program = ServerProgram(num_repetitions=2)

    results = run(cfg, {"client": client_program, "server": server_program}, num_times)

    print(results)
