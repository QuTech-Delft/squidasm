from typing import Generator

from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


class AliceProtocol(BlueprintProtocol):
    def __init__(self, peer: str, num_epr_pairs: int):
        super().__init__()
        self.peer = peer
        self.num_epr_pairs = num_epr_pairs
        self._logger = None

    def run(self) -> Generator[EventExpression, None, None]:
        self._logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}_{self.context.node.name}"
        )
        socket = self.context.sockets[self.peer]
        egp = self.context.egp[self.peer]
        qdevice = self.context.node.qdevice

        for i in range(self.num_epr_pairs):
            # Do a classical message exchange first
            message = yield from socket.recv()
            self._logger.info(f"{self.context.node.name} receives: {message}")

            # Place a request to the EGP
            request = ReqCreateAndKeep(
                remote_node_id=self.context.node_id_mapping[self.peer], number=1
            )
            egp.put(request)

            # Wait for EGP to be finished
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )
            # Measure qubit
            received_qubit_mem_pos = response.logical_qubit_id
            result = qdevice.measure(received_qubit_mem_pos)[0]
            qdevice.discard(received_qubit_mem_pos)

            self._logger.info(
                f"pair: {i} {self.context.node.name} Created EPR with {self.peer} and measures {result}"
            )


class BobProtocol(BlueprintProtocol):
    def __init__(self, peer: str, num_epr_pairs: int):
        super().__init__()
        self.peer = peer
        self.num_epr_pairs = num_epr_pairs
        self._logger = None

    def run(self) -> Generator[EventExpression, None, None]:
        self._logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}_{self.context.node.name}"
        )

        egp = self.context.egp[self.peer]
        socket = self.context.sockets[self.peer]
        qdevice = self.context.node.qdevice

        # Place a receive request at start, after this Bob is always open to create entanglement with Eve
        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.peer]))

        for i in range(self.num_epr_pairs):
            # Classical message exchange
            msg = "Ready to start entanglement"
            socket.send(msg)
            self._logger.info(f"{self.context.node.name} sends: {msg}")

            # Wait for a signal from the EGP.
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )
            received_qubit_mem_pos = response.logical_qubit_id

            # measure result
            result = qdevice.measure(positions=[received_qubit_mem_pos])[0]
            qdevice.discard(received_qubit_mem_pos)
            self._logger.info(
                f"pair: {i} {self.context.node.name} Created EPR with {self.peer} and measures {result}"
            )
