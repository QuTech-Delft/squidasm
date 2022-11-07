from typing import Generator, List

import netsquid as ns
import numpy as np
from netsquid.protocols import Protocol
from netsquid.qubits import qubitapi
from netsquid.qubits.qubit import Qubit

from pydynaa import EventExpression


def yield_from(generator: Generator):
    try:
        while True:
            next(generator)
    except StopIteration as e:
        return e.value


class SimpleNetSquidProtocol(Protocol):
    def __init__(self, generator: Generator) -> None:
        super().__init__("test")
        self._gen = generator
        self.result = None

    def run(self) -> Generator[EventExpression, None, None]:
        self.result = yield from self._gen


def netsquid_run(generator: Generator):
    prot = SimpleNetSquidProtocol(generator)
    prot.start()
    ns.sim_run()
    return prot.result


def text_equal(text1, text2) -> bool:
    # allows whitespace differences
    lines1 = [line.strip() for line in text1.split("\n") if len(line) > 0]
    lines2 = [line.strip() for line in text2.split("\n") if len(line) > 0]
    for line1, line2 in zip(lines1, lines2):
        if line1 != line2:
            return False
    return True


def has_state(qubit: Qubit, state: np.ndarray, margin: float = 0.001) -> bool:
    return abs(1.0 - qubitapi.fidelity(qubit, state, squared=True)) < margin


def has_multi_state(
    qubits: List[Qubit], state: np.ndarray, margin: float = 0.001
) -> bool:
    return abs(1.0 - qubitapi.fidelity(qubits, state, squared=True)) < margin


def has_max_mixed_state(qubit: Qubit, margin: float = 0.001) -> bool:
    # TODO: fix fidelity calculation with mixed states
    max_mixed = np.array([[0.5, 0], [0, 0.5]])
    # qubit_state = qubitapi.reduced_dm(qubit)
    return np.isclose(qubitapi.reduced_dm(qubit), max_mixed, margin)
