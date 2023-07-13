import random
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import numpy
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.classical_communication.socket import Socket

from pydynaa import EventExpression
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
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="QKD_program",
            csockets=[self._peer_name],
            epr_sockets=[self._peer_name],
            max_qubits=1,
        )

    def __init__(self, num_bits: int, is_client: bool):
        self._num_bits = num_bits
        self._buf_msgs = []
        self._is_client = is_client
        self._peer_name = "server" if is_client else "client"

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self._peer_name]

        num_test_bits = max(self._num_bits // 4, 1)

        outcomes, bases = yield from self.distribute_states(context)

        pairs_info = []
        for i in range(self._num_bits):
            pairs_info.append(
                PairInfo(
                    index=i,
                    basis=bases[i],
                    outcome=outcomes[i],
                )
            )

        if not self._is_client:
            csocket.send(ALL_MEASURED)
        else:
            m = yield from csocket.recv()
            if m != ALL_MEASURED:
                raise RuntimeError("Failed to distribute BB84 states")

        pairs_info = yield from self.filter_bases(csocket, pairs_info)

        pairs_info, error_rate = yield from self.estimate_error_rate(
            csocket, pairs_info, num_test_bits
        )

        raw_key = [
            pair.outcome
            for pair in pairs_info
            if pair.same_basis and not pair.test_outcome
        ]

        return {"raw_key": raw_key, "error_rate": error_rate}

    def distribute_states(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Tuple[List[int], List[int]]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self._peer_name]

        outcomes = [numpy.nan for _ in range(self._num_bits)]
        bases = [random.randint(0, 1) for _ in range(self._num_bits)]

        for i in range(self._num_bits):
            if self._is_client:
                q = epr_socket.create_keep(1)[0]
            else:
                q = epr_socket.recv_keep(1)[0]
            if bases[i] == 1:
                q.H()
            m = q.measure()
            yield from conn.flush()
            outcomes[i] = int(m)

        outcomes = [int(b) for b in outcomes]
        bases = [int(b) for b in bases]
        return outcomes, bases

    def filter_bases(self, socket: Socket, pairs_info: List[PairInfo]):
        bases = [(i, pairs_info[i].basis) for (i, pair) in enumerate(pairs_info)]

        if self._is_client:
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
        socket: Socket,
        pairs_info: List[PairInfo],
        num_test_bits: int,
    ):
        if self._is_client:
            same_basis_indices = [pair.index for pair in pairs_info if pair.same_basis]
            test_indices = random.sample(
                same_basis_indices, min(num_test_bits, len(same_basis_indices))
            )
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            socket.send_structured(StructuredMessage("Test indices", test_indices))
            target_test_outcomes = (yield from socket.recv_structured()).payload
            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
        else:
            test_indices = (yield from socket.recv_structured()).payload
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
            target_test_outcomes = (yield from socket.recv_structured()).payload

        num_error = 0
        for (i1, t1), (i2, t2) in zip(test_outcomes, target_test_outcomes):
            assert i1 == i2
            if t1 != t2:
                num_error += 1
                pairs_info[i1].same_outcome = False
            else:
                pairs_info[i1].same_outcome = True

        return pairs_info, (num_error / num_test_bits)
