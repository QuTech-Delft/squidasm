from dataclasses import dataclass, field
from typing import Generator, List

import netsquid as ns
from netsquid_netbuilder.protocol_base import BlueprintProtocol

from pydynaa import EventExpression


@dataclass
class ClassicalMessageEventInfo:
    time: float
    peer: str
    msg: str


@dataclass
class ClassicalMessageEventRegistration:
    sent: List[ClassicalMessageEventInfo] = field(default_factory=list)
    received: List[ClassicalMessageEventInfo] = field(default_factory=list)


class ClassicalSenderProtocol(BlueprintProtocol):
    def __init__(
        self,
        peer: str,
        result_reg: ClassicalMessageEventRegistration,
        messages: List[str],
        send_times: List[float],
    ):
        super().__init__()
        assert len(messages) == len(send_times)
        self.peer = peer
        self.result_reg = result_reg
        self.messages = messages
        self.send_times = send_times

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.peer]

        for send_time, message in zip(self.send_times, self.messages):
            yield self.await_timer(end_time=send_time)
            port.tx_output(message)
            self.result_reg.sent.append(
                ClassicalMessageEventInfo(ns.sim_time(), self.peer, message)
            )


class ClassicalReceiverProtocol(BlueprintProtocol):
    def __init__(self, peer: str, result_reg: ClassicalMessageEventRegistration):
        super().__init__()
        self.peer = peer
        self.result_reg = result_reg

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.peer]

        while True:
            yield self.await_port_input(port)
            message = port.rx_input()
            self.result_reg.received.append(
                ClassicalMessageEventInfo(ns.sim_time(), self.peer, message.items[0])
            )
