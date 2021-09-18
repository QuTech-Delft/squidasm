from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from netsquid.qubits.qubit import Qubit

if TYPE_CHECKING:
    from squidasm.sim.stack.stack import StackNetwork

T_QubitData = Dict[str, Dict[int, Qubit]]


class GlobalSimData:
    _NETWORK: Optional[StackNetwork] = None

    @classmethod
    def set_network(cls, network: StackNetwork) -> None:
        cls._NETWORK = network

    @classmethod
    def get_network(cls) -> Optional[StackNetwork]:
        return cls._NETWORK

    @classmethod
    def get_quantum_state(cls) -> T_QubitData:
        network = cls.get_network()
        assert network is not None

        qubits: T_QubitData = {}
        for name, qdevice in network.qdevices.items():
            qubits[name] = {}
            for i in range(qdevice.num_positions):
                if qdevice.mem_positions[i].in_use:
                    [q] = qdevice.peek(i, skip_noise=True)
                    qubits[name][i] = q
        return qubits
