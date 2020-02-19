import logging
from queue import Empty

import netsquid as ns
from pydynaa import EventType, EventExpression
from netsquid.protocols import NodeProtocol
from squidasm.processor import NetSquidProcessor
from squidasm.queues import get_queue, Signal
from squidasm.network_setup import get_node


class SubroutineHandler(NodeProtocol):
    def __init__(self, node, run_once=False):
        super().__init__(node=node)
        self._processor = NetSquidProcessor(
            name=node.name,
            qdevice=self.node.qmemory,
        )

        self._subroutine_queue = get_queue(self.node.name)

        self._run_once = run_once

        self._loop_event = EventType("LOOP", "event for looping without blocking")

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.node.name})")

    def run(self):
        while self.is_running:
            yield from self._execute_next_subroutine()

    def _execute_next_subroutine(self):
        self._logger.debug(f"SubroutineHandler at node {self.node} fetching item in the queue")
        item = yield from self._fetch_next_item()
        if isinstance(item, Signal):
            self._logger.debug(f"SubroutineHandler at node {self.node} handles the signal {item}")
            self._handle_signal(signal=item)
        else:
            self._logger.debug(f"SubroutineHandler at node {self.node} executing next subroutine "
                               f"from app ID {item.app_id}")
            yield from self._execute_instructions(instructions=item.instructions)
            self._logger.debug(f"SubroutineHandler at node {self.node} marking subroutine as done")
            self._task_done()

    def _fetch_next_item(self):
        while True:
            try:
                item = self._subroutine_queue.get(block=False)
            except Empty:
                self._schedule_now(self._loop_event)
                yield EventExpression(source=self, event_type=self._loop_event)
            else:
                return item

    def _execute_instructions(self, instructions):
        yield from self._processor.execute_instructions(instructions=instructions)

    def _task_done(self):
        self._subroutine_queue.task_done()

    def _handle_signal(self, signal):
        if signal == Signal.STOP:
            self._logger.debug(f"SubroutineHandler at node {self.node} stops")
            self.stop()
        else:
            raise ValueError(f"Unkown signal {signal}")


def test():
    logging.basicConfig(level=logging.DEBUG)
    alice = get_node(name="Alice", num_qubits=5)
    subroutine_handler = SubroutineHandler(alice)

    # Put subroutine in queue
    queue = get_queue(alice.name)
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q @0
creg(1) m
qreg(1) q!
init q!
op! q! // this is a comment
meas q! m
beq m[0] 0 EXIT
x q!
EXIT:
output m
// this is also a comment
"""
    queue.put(subroutine)
    # Make sure to signal to stop after
    queue.put(Signal.STOP)

    # Starting subroutine
    subroutine_handler.start()

    # Starting netsquid
    ns.sim_run()

    output_data = subroutine_handler._processor.output_data
    assert len(output_data) == 1
    assert output_data[0].address == 1
    assert len(output_data[0].data) == 1
    assert output_data[0].data[0] in [0, 1]


if __name__ == '__main__':
    test()
