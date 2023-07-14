from typing import Generator, List

import netsquid as ns
from netsquid_netbuilder.protocol_base import BlueprintProtocol

from pydynaa import EventExpression


class ClassicalMessageResultRegistration:
    def __init__(self):
        self.send_classical_msg: List[(float, str)] = []
        self.rec_classical_msg: List[(float, str)] = []


class AliceProtocol(BlueprintProtocol):
    PEER = "Bob"

    def __init__(
        self,
        result_reg: ClassicalMessageResultRegistration,
        messages: List[str],
        send_times: List[float],
    ):
        super().__init__()
        assert len(messages) == len(send_times)
        self.result_reg = result_reg
        self.messages = messages
        self.send_times = send_times

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.PEER]

        for send_time, message in zip(self.send_times, self.messages):
            yield self.await_timer(end_time=send_time)
            port.tx_output(message)
            self.result_reg.send_classical_msg.append((ns.sim_time(), message))


class BobProtocol(BlueprintProtocol):
    PEER = "Alice"

    def __init__(self, result_reg: ClassicalMessageResultRegistration):
        super().__init__()
        self.result_reg = result_reg

    def run(self) -> Generator[EventExpression, None, None]:
        port = self.context.ports[self.PEER]

        while True:
            yield self.await_port_input(port)
            message = port.rx_input()
            self.result_reg.rec_classical_msg.append((ns.sim_time(), message.items[0]))
