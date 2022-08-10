from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
from netsquid.qubits import qubitapi
from netsquid.qubits.qubit import Qubit

if TYPE_CHECKING:
    from squidasm.sim.stack.stack import StackNetwork

T_QubitData = Dict[str, Dict[int, Qubit]]
T_StateData = Dict[str, Dict[int, np.ndarray]]


class GlobalSimData:
    _NETWORK: Optional[StackNetwork] = None
    _BREAKPOINT_STATES: List[np.ndarray] = []

    @classmethod
    def set_network(cls, network: StackNetwork) -> None:
        cls._NETWORK = network

    @classmethod
    def get_network(cls) -> Optional[StackNetwork]:
        return cls._NETWORK

    @classmethod
    def get_quantum_state(cls, save: bool = False) -> T_QubitData:
        network = cls.get_network()
        assert network is not None

        qubits: T_QubitData = {}
        states: T_StateData = {}
        for name, qdevice in network.qdevices.items():
            qubits[name] = {}
            states[name] = {}
            for i in range(qdevice.num_positions):
                if qdevice.mem_positions[i].in_use:
                    [q] = qdevice.peek(i, skip_noise=True)
                    qubits[name][i] = q
                    if save:
                        states[name][i] = qubitapi.reduced_dm(q)
        if save:
            cls._BREAKPOINT_STATES.append(states)
        return qubits

    @classmethod
    def get_last_breakpoint_state(cls) -> np.ndarray:
        assert len(cls._BREAKPOINT_STATES) > 0
        return cls._BREAKPOINT_STATES[-1]
