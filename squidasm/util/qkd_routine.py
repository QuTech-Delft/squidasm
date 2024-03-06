import random
from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple

from bitarray import bitarray
from netqasm.sdk.classical_communication.message import StructuredMessage

from pydynaa import EventExpression
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import ProgramContext


@dataclass
class _PairInfo:
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


class QKDRoutine:
    @staticmethod
    def _distribute_states(
        context: ProgramContext, is_init: bool, peer_name: str, num_epr: int
    ) -> Generator[EventExpression, None, List[_PairInfo]]:
        """
        Generates and measures a number of entangled qubits in a random basis.
        :param context: Local program context
        :param is_init: Flag to designate if this node started the protocol
        :return: List of PairInfo with index, outcome and basis per measurement.
        """
        conn = context.connection
        epr_socket = context.epr_sockets[peer_name]

        results = []

        for i in range(num_epr):
            basis = random.randint(0, 1)
            if is_init:
                q = epr_socket.create_keep(1)[0]
            else:
                q = epr_socket.recv_keep(1)[0]
            if basis == 1:
                q.H()
            m = q.measure()
            yield from conn.flush()
            results.append(_PairInfo(index=i, outcome=int(m), basis=basis))

        return results

    @staticmethod
    def _filter_bases(
        socket: ClassicalSocket, pairs_info: List[_PairInfo], is_init: bool
    ) -> Generator[EventExpression, None, List[_PairInfo]]:
        """
        Communicates the random base choices with the peer and filters out the measured entangled qubits
         that where measured in a different basis.
        :param socket: classical socket to peer.
        :param pairs_info: List of PairInfo object containing relevant information for the measured entangled qubits
        :param is_init: Flag to designate if this node started the protocol
        :return: List of PairInfo with the same_basis field filled in.
        """
        bases = [(i, pairs_info[i].basis) for (i, pair) in enumerate(pairs_info)]

        if is_init:
            socket.send_structured(StructuredMessage("Bases", bases))
            remote_bases = (yield from socket.recv_structured()).payload
        else:
            remote_bases = (yield from socket.recv_structured()).payload
            socket.send_structured(StructuredMessage("Bases", bases))

        for (i, basis), (remote_i, remote_basis) in zip(bases, remote_bases):
            assert i == remote_i
            pairs_info[i].same_basis = basis == remote_basis

        return pairs_info

    @staticmethod
    def _estimate_error_rate(
        socket: ClassicalSocket,
        pairs_info: List[_PairInfo],
        num_test_bits: int,
        is_init: bool,
    ) -> Generator[EventExpression, None, Tuple[List[_PairInfo], float]]:
        """
        Estimates the error rate for the raw key, by choosing a random subset of the key to exchange with the peer.
        :param socket: classical socket to peer.
        :param pairs_info: List of PairInfo object containing relevant information for the measured entangled qubits
        :param num_test_bits: The amount bits from the raw key to use for the estimation.
        :param is_init: Flag to designate if this node started the protocol
        :return: Tuple with list of PairInfo and the estimated error rate
        """
        if is_init:
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

    @classmethod
    def run(
        cls,
        context: ProgramContext,
        peer_name: str,
        is_init: bool,
        num_epr: int,
        num_test_bits: int = None,
    ) -> Generator[EventExpression, None, Tuple[bitarray, float]]:
        """
        Run the QKD routine. The routine will return a variable length raw key and the error rate estimation.
        The length of the variable key has an expectation value of num_epr/2 - num_tests_bits.
        The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

        :param context: context: context of the current program
        :param peer_name: name of the peer engaging in this teleportation protocol
        :param is_init: Flag to designate if this node started the protocol.
         The peer must use the opposite flag for this protocol to work.
        :param context: Local program context
        :param num_epr: The number of EPR pairs to be generated.
        :param num_test_bits: The amount of EPR pairs in the same basis to use from the raw key
         to use for the error estimation. The EPR pairs used for the error estimation are not used for the raw key.
        :return: A tuple with a bitarray containing the raw key and a float that is the error rate estimation.
        """
        num_test_bits = num_epr // 4 if num_test_bits is None else num_test_bits
        csocket = context.csockets[peer_name]

        pairs_info = yield from cls._distribute_states(
            context, is_init, peer_name, num_epr
        )

        pairs_info = yield from cls._filter_bases(csocket, pairs_info, is_init)

        pairs_info, error_rate = yield from cls._estimate_error_rate(
            csocket, pairs_info, num_test_bits, is_init
        )

        raw_key = [
            pair.outcome
            for pair in pairs_info
            if pair.same_basis and not pair.test_outcome
        ]

        return bitarray(raw_key), error_rate
