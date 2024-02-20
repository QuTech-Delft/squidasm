from dataclasses import dataclass, field
from typing import Generator, List

import netsquid as ns
import numpy as np

from netsquid_driver.entanglement_tracker_service import EntanglementTrackerService
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from netsquid_netbuilder.util.test_protocol_clink import ClassicalMessageEventInfo
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


@dataclass
class EGPEventInfo:
    time: float
    node_name: str
    peer_name: str
    result: ResCreateAndKeep
    dm: np.ndarray


@dataclass
class EGPEventRegistration:
    received_classical: List[ClassicalMessageEventInfo] = field(default_factory=list)
    received_egp: List[EGPEventInfo] = field(default_factory=list)


class EGPCreateProtocol(BlueprintProtocol):
    def __init__(
        self,
        peer: str,
        result_reg: EGPEventRegistration,
        n_epr: int = 1,
        minimum_fidelity=0,
    ):
        super().__init__()
        self.peer = peer
        self.result_reg = result_reg
        self.n_epr = n_epr
        self.minimum_fidelity = minimum_fidelity

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node
        socket = self.context.sockets[self.peer]
        egp = self.context.egp[self.peer]

        # Wait for classical message in order to delay the egp request to peer
        message = yield from socket.recv()
        self.result_reg.received_classical.append(
            ClassicalMessageEventInfo(ns.sim_time(), self.peer, message)
        )

        for _ in range(self.n_epr):
            # create request
            request = ReqCreateAndKeep(
                remote_node_id=self.context.node_id_mapping[self.peer],
                number=1,
                minimum_fidelity=self.minimum_fidelity,
            )
            egp.put(request)

            # Await request completion
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response: ResCreateAndKeep = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )

            # register result
            qubit_mem_pos = response.logical_qubit_id
            qubit = node.qdevice.peek(positions=qubit_mem_pos)[0]
            qubit_dm = ns.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
            self.result_reg.received_egp.append(
                EGPEventInfo(ns.sim_time(), node.name, self.peer, response, qubit_dm)
            )

            # Free qubit
            node.qdevice.discard(qubit_mem_pos)
            node.driver[EntanglementTrackerService].register_local_discard_mem_pos(qubit_mem_pos)


class EGPReceiveProtocol(BlueprintProtocol):
    def __init__(self, peer: str, result_reg: EGPEventRegistration, n_epr: int = 1):
        super().__init__()
        self.peer = peer
        self.result_reg = result_reg
        self.n_epr = n_epr

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node
        socket = self.context.sockets[self.peer]
        egp = self.context.egp[self.peer]

        msg = "test_msg"
        socket.send(msg)

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.peer]))

        for _ in range(self.n_epr):
            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )

            # register result
            qubit_mem_pos = response.logical_qubit_id
            qubit = node.qdevice.peek(positions=qubit_mem_pos)[0]
            qubit_dm = ns.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
            self.result_reg.received_egp.append(
                EGPEventInfo(ns.sim_time(), node.name, self.peer, response, qubit_dm)
            )

            # Free qubit
            node.qdevice.discard(qubit_mem_pos)
            node.driver[EntanglementTrackerService].register_local_discard_mem_pos(qubit_mem_pos)
