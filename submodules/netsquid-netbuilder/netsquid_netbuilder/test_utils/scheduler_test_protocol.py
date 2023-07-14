from dataclasses import dataclass
from typing import Generator, List

import netsquid as ns
from netsquid_netbuilder.network import ProtocolContext
from netsquid_netbuilder.protocol_base import BlueprintProtocol
from qlink_interface import ReqCreateAndKeep, ReqReceive, ResCreateAndKeep

from pydynaa import EventExpression


@dataclass
class SchedulerRequest:
    submit_time: float
    sender_name: str
    receiver_name: str


@dataclass
class SchedulerResult:
    node_1: str
    node_2: str
    completion_time: float
    epr_measure_result: int


class SchedulerResultRegistration:
    def __init__(self):
        self.results: List[SchedulerResult] = []


class SchedulerTestProtocol(BlueprintProtocol):
    def __init__(
        self, result_reg: SchedulerResultRegistration, requests: List[SchedulerRequest]
    ):
        super().__init__()
        self.result_reg = result_reg
        self.requests = requests
        self.sender_protocol = EGPSenderProtocol(requests)
        self.receiver_protocol = EGPReceiverProtocol(requests)
        self.egp_listeners: List[EGPListener] = []
        self.add_subprotocol(self.sender_protocol)
        self.add_subprotocol(self.receiver_protocol)

    def set_context(self, context: ProtocolContext):
        super().set_context(context)
        self.setup_egp_listeners()
        self.sender_protocol.set_context(context)
        self.receiver_protocol.set_context(context)
        for egp_listener in self.egp_listeners:
            egp_listener.set_context(context)

    def start(self):
        super().start()
        self.sender_protocol.start()
        self.receiver_protocol.start()
        for egp_listener in self.egp_listeners:
            egp_listener.start()

    def stop(self):
        super().stop()
        self.sender_protocol.stop()
        self.receiver_protocol.stop()
        for egp_listener in self.egp_listeners:
            egp_listener.stop()

    def setup_egp_listeners(self):
        for remote_node_name, _ in self.context.egp.items():
            egp_listener = EGPListener(self.result_reg, remote_node_name)
            self.egp_listeners.append(egp_listener)
            self.add_subprotocol(egp_listener)


class EGPSenderProtocol(BlueprintProtocol):
    def __init__(self, requests: List[SchedulerRequest]):
        super().__init__()
        self.requests = requests

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node

        for request in self.requests:
            # Ignore the request if this node is not part of the request
            if node.name != request.sender_name:
                continue

            # Wait until requests,
            # add a small offset to ensure that the receiver is the first to submit a listing request
            time_offset = 1e-18
            yield self.await_timer(end_time=request.submit_time + time_offset)

            peer = request.receiver_name
            egp = self.context.egp[peer]
            # create request
            request = ReqCreateAndKeep(
                remote_node_id=self.context.node_id_mapping[peer], number=1
            )
            egp.put(request)


class EGPReceiverProtocol(BlueprintProtocol):
    def __init__(self, requests: List[SchedulerRequest]):
        super().__init__()
        self.requests = requests

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node

        for request in self.requests:
            # Ignore the request if this node is not part of the request
            if node.name != request.receiver_name:
                continue

            # Wait until requests time comes up
            yield self.await_timer(end_time=request.submit_time)

            peer = request.sender_name
            egp = self.context.egp[peer]
            # create receive request
            request = ReqReceive(remote_node_id=self.context.node_id_mapping[peer])
            egp.put(request)


class EGPListener(BlueprintProtocol):
    def __init__(self, result_reg: SchedulerResultRegistration, remote_node_name: str):
        super().__init__()
        self.remote_node_name = remote_node_name
        self.result_reg = result_reg

    def run(self):
        node = self.context.node
        egp = self.context.egp[self.remote_node_name]

        while True:
            yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
            response: ResCreateAndKeep = egp.get_signal_result(
                label=ResCreateAndKeep.__name__, receiver=self
            )

            qubit_mem_pos = response.logical_qubit_id
            measure_result = node.qdevice.measure(positions=qubit_mem_pos)[0]
            node.qdevice.discard(qubit_mem_pos)

            result = SchedulerResult(
                node_1=node.name,
                node_2=self.remote_node_name,
                completion_time=ns.sim_time(),
                epr_measure_result=measure_result,
            )

            self.result_reg.results.append(result)
