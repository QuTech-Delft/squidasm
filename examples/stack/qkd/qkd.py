import logging
import os
import random
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

from netqasm.logging.glob import get_netqasm_logger, set_log_level
from netqasm.sdk.classical_communication.message import StructuredMessage

from pydynaa import EventExpression
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

ALL_MEASURED = "All qubits measured"


@dataclass
class PairInfo:
    """Information that a node has about one generated pair.
    The information is filled progressively during the protocol."""

    # Index in list of all generated pairs.
    index: int

    # Basis this node measured in. 0 = Z, 1 = X.
    basis: int

    # Measurement outcome (0 or 1).
    outcome: int

    # Whether the other node measured his qubit in the same basis or not.
    same_basis: Optional[bool] = None

    # Whether to use this pair to estimate errors by comparing the outcomes.
    test_outcome: Optional[bool] = None

    # Whether measurement outcome is the same as the other node's.
    # (Only for pairs used for error estimation.)
    same_outcome: Optional[bool] = None


class QkdProgram(Program):
    def __init__(self, num_bits: int):
        self._num_bits = num_bits
        self._buf_msgs = []

    def distribute_states(
        self, context: ProgramContext, create: bool
    ) -> Generator[EventExpression, None, Tuple[List[int], List[int]]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        outcomes = [None for _ in range(self._num_bits)]
        bases = [random.randint(0, 1) for _ in range(self._num_bits)]

        for i in range(self._num_bits):
            if create:
                q = epr_socket.create(1)[0]
            else:
                q = epr_socket.recv(1)[0]
            if bases[i] == 1:
                q.H()
            m = q.measure()
            yield from conn.flush()
            outcomes[i] = int(m)

        outcomes = [int(b) for b in outcomes]
        bases = [int(b) for b in bases]
        return outcomes, bases

    def filter_bases(
        self, socket: ClassicalSocket, pairs_info: List[PairInfo], create: bool
    ):
        bases = [(i, pairs_info[i].basis) for (i, pair) in enumerate(pairs_info)]

        if create:
            socket.send_structured(StructuredMessage("Bases", bases))
            remote_bases = (yield from socket.recv_structured()).payload
        else:
            remote_bases = (yield from socket.recv_structured()).payload
            socket.send_structured(StructuredMessage("Bases", bases))

        for (i, basis), (remote_i, remote_basis) in zip(bases, remote_bases):
            assert i == remote_i
            pairs_info[i].same_basis = basis == remote_basis

        return pairs_info

    def estimate_error_rate(
        self,
        socket: ClassicalSocket,
        pairs_info: List[PairInfo],
        num_test_bits: int,
        create: bool,
    ):
        if create:
            same_basis_indices = [pair.index for pair in pairs_info if pair.same_basis]
            test_indices = random.sample(
                same_basis_indices, min(num_test_bits, len(same_basis_indices))
            )
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            print(f"{self.meta.name} finding {num_test_bits} test bits")
            print(f"{self.meta.name} test indices: {test_indices}")
            print(f"{self.meta.name} test outcomes: {test_outcomes}")

            socket.send_structured(StructuredMessage("Test indices", test_indices))
            target_test_outcomes = (yield from socket.recv_structured()).payload
            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
            print(f"{self.meta.name} target_test_outcomes: {target_test_outcomes}")
        else:
            test_indices = (yield from socket.recv_structured()).payload
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            print(f"{self.meta.name} test indices: {test_indices}")
            print(f"{self.meta.name} test outcomes: {test_outcomes}")

            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
            target_test_outcomes = (yield from socket.recv_structured()).payload
            print(f"{self.meta.name} target_test_outcomes: {target_test_outcomes}")

        num_error = 0
        for (i1, t1), (i2, t2) in zip(test_outcomes, target_test_outcomes):
            assert i1 == i2
            if t1 != t2:
                num_error += 1
                pairs_info[i1].same_outcome = False
            else:
                pairs_info[i1].same_outcome = True

        return pairs_info, (num_error / num_test_bits)


class AliceProgram(QkdProgram):
    PEER = "bob"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_program",
            parameters={"num_bits": self._num_bits},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]

        num_test_bits = max(num_bits // 4, 1)

        outcomes, bases = yield from self.distribute_states(context, True)
        print(f"alice: outcomes = {outcomes}, bases = {bases}")

        pairs_info = []
        for i in range(num_bits):
            pairs_info.append(
                PairInfo(
                    index=i,
                    basis=bases[i],
                    outcome=outcomes[i],
                )
            )

        m = yield from csocket.recv()
        if m != ALL_MEASURED:
            raise RuntimeError("Failed to distribute BB84 states")

        # print(f"alice pairs info before filter:\n")
        # print(pairs_info)
        pairs_info = yield from self.filter_bases(csocket, pairs_info, True)
        # print(f"alice pairs info after filter:\n")
        # print(pairs_info)

        for pair in pairs_info:
            if pair.same_basis:
                print(f"alice same basis: {pair.index}, {pair.outcome}")

        pairs_info, error_rate = yield from self.estimate_error_rate(
            csocket, pairs_info, num_test_bits, True
        )
        print(f"alice error rate: {error_rate}")

        raw_key = [
            pair.outcome
            for pair in pairs_info
            if pair.same_basis and not pair.test_outcome
        ]
        print(f"alice raw key: {raw_key}")

        return {"raw_key": raw_key}


class BobProgram(QkdProgram):
    PEER = "alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_program",
            parameters={"num_bits": self._num_bits},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]

        num_test_bits = max(num_bits // 4, 1)

        outcomes, bases = yield from self.distribute_states(context, False)
        print(f"bob  : outcomes = {outcomes}, bases = {bases}")

        pairs_info = []
        for i in range(num_bits):
            pairs_info.append(
                PairInfo(
                    index=i,
                    basis=bases[i],
                    outcome=outcomes[i],
                )
            )

        csocket.send(ALL_MEASURED)

        # print(f"bob pairs info before filter:\n")
        # print(pairs_info)
        pairs_info = yield from self.filter_bases(csocket, pairs_info, False)
        # print(f"bob pairs info after filter:\n")
        # print(pairs_info)

        for pair in pairs_info:
            if pair.same_basis:
                print(f"bob   same basis: {pair.index}, {pair.outcome}")

        pairs_info, error_rate = yield from self.estimate_error_rate(
            csocket, pairs_info, num_test_bits, False
        )
        print(f"bob error_rate: {error_rate}")

        raw_key = [
            pair.outcome
            for pair in pairs_info
            if pair.same_basis and not pair.test_outcome
        ]
        print(f"bob raw key: {raw_key}")

        return {"raw_key": raw_key}


if __name__ == "__main__":
    set_log_level("WARNING")
    fileHandler = logging.FileHandler("{0}/{1}.log".format(".", "debug"), mode="w")
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    fileHandler.setFormatter(formatter)
    get_netqasm_logger().addHandler(fileHandler)

    num_times = 1

    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__), "config.yaml")
    )

    num_bits = 100

    alice_program = AliceProgram(num_bits=num_bits)
    bob_program = BobProgram(num_bits=num_bits)

    alice_results, bob_results = run(
        cfg, {"alice": alice_program, "bob": bob_program}, num_times
    )

    for i, (alice_result, bob_result) in enumerate(zip(alice_results, bob_results)):
        print(f"run {i}:")
        rk_alice = "".join(str(b) for b in alice_result["raw_key"])
        rk_bob = "".join(str(b) for b in bob_result["raw_key"])
        print(f"alice raw key: {rk_alice}")
        print(f"bob   raw key: {rk_bob}")
