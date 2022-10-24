from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
from netsquid.qubits import qubitapi
from netsquid.qubits.qubit import Qubit

if TYPE_CHECKING:
    from squidasm.qoala.sim.network import ProcNodeNetwork

T_QubitData = Dict[str, Dict[int, Qubit]]
T_StateData = Dict[str, Dict[int, np.ndarray]]


class GlobalSimData:
    _NETWORK: Optional[ProcNodeNetwork] = None
    _BREAKPOINT_STATES: List[T_StateData] = []

    def set_network(self, network: ProcNodeNetwork) -> None:
        self._NETWORK = network

    def get_network(self) -> Optional[ProcNodeNetwork]:
        return self._NETWORK

    def get_quantum_state(self, save: bool = False) -> T_QubitData:
        network = self.get_network()
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
            self._BREAKPOINT_STATES.append(states)
        return qubits

    def get_last_breakpoint_state(self) -> T_StateData:
        assert len(self._BREAKPOINT_STATES) > 0
        return self._BREAKPOINT_STATES[-1]
