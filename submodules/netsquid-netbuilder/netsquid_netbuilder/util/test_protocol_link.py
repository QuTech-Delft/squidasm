from typing import Any, Generator, List

import netsquid as ns
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


class ResultRegistration:
    def __init__(self):
        self.rec_classical_msg: List[(float, str)] = []
        self.rec_egp_results: List[(float, ResCreateAndKeep, Any)] = []


class AliceProtocol(BlueprintProtocol):
    PEER = "Bob"

    def __init__(self, result_reg: ResultRegistration, n_epr: int = 1):
        super().__init__()
        self.result_reg = result_reg
        self.n_epr = n_epr

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node
        port = self.context.ports[self.PEER]
        egp = self.context.egp[self.PEER]

        for _ in range(self.n_epr):
            # Wait for classical message in order to delay the egp request to
            yield self.await_port_input(port)
            message = port.rx_input()
            self.result_reg.rec_classical_msg.append((ns.sim_time(), message.items[0]))

            # create request
            request = ReqCreateAndKeep(
                remote_node_id=self.context.node_id_mapping[self.PEER], number=1
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
            self.result_reg.rec_egp_results.append((ns.sim_time(), response, qubit_dm))

            # Free qubit
            node.qdevice.discard(qubit_mem_pos)


class BobProtocol(BlueprintProtocol):
    PEER = "Alice"

    def __init__(self, result_reg: ResultRegistration, n_epr: int = 1):
        super().__init__()
        self.result_reg = result_reg
        self.n_epr = n_epr

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node
        port = self.context.ports[self.PEER]
        egp = self.context.egp[self.PEER]

        for _ in range(self.n_epr):
            msg = "test_msg"
            port.tx_output(msg)

            egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))

            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )

            # register result
            qubit_mem_pos = response.logical_qubit_id
            qubit = node.qdevice.peek(positions=qubit_mem_pos)[0]
            qubit_dm = ns.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
            self.result_reg.rec_egp_results.append((ns.sim_time(), response, qubit_dm))

            # Free qubit
            node.qdevice.discard(qubit_mem_pos)
