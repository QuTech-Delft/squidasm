import logging

from squidasm.queues import get_queue, Signal
from squidasm.run import run_applications
from squidasm.sdk import Message, InitNewAppMessage, MessageType
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.parser import Parser


class SimpleCommunicator:
    def __init__(self, node_name, subroutine, app_id=0, max_qubits=5):
        self._subroutine = Parser(subroutine).subroutine
        self._node_name = node_name
        self._subroutine_queue = get_queue(node_name)
        self._init_new_app(app_id=app_id, max_qubits=max_qubits)

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self._node_name})")

    def _init_new_app(self, app_id, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._subroutine_queue.put(Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=app_id,
                max_qubits=max_qubits,
            ),
        ))

    def run(self, num_times=1):
        for _ in range(num_times):
            self._submit_subroutine()
        self._signal_stop()

    def _submit_subroutine(self):
        self._logger.debug(f"SimpleCommunicator for node {self._node_name} puts the next subroutine")
        self._subroutine_queue.put(Message(type=MessageType.SUBROUTINE, msg=self._subroutine))

    def _signal_stop(self):
        self._subroutine_queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))
        self._subroutine_queue.join()


def test():
    logging.basicConfig(level=logging.DEBUG)
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE op h
# DEFINE q q0
qtake q!
init q!
op! q! // this is a comment
meas q! m
beq m 0 EXIT
x q!
EXIT:
// this is also a comment
"""
    print("Applications at Alice and Bob will submit the following subroutine to QDevice:")
    print(subroutine)
    print()

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        communicator = SimpleCommunicator("Bob", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Bob thread")

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })


def test_meas_many():
    logging.basicConfig(level=logging.DEBUG)
    subroutine = """
# NETQASM 0.0
# APPID 0
array(10) ms
store i 0
LOOP:
beq i 10 EXIT
qtake q
init q
h q
meas q ms[]
qfree q
add i i 1
beq 0 0 LOOP
EXIT:
// this is also a comment
"""
    print("Applications at Alice will submit the following subroutine to QDevice:")
    print(subroutine)
    print()

    def run_alice():
        logging.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutine=subroutine)
        communicator.run(num_times=1)
        logging.debug("End Alice thread")

    run_applications({
        "Alice": run_alice,
    })

    shared_memory = get_shared_memory("Alice", key=0)
    print(shared_memory)


if __name__ == '__main__':
    test_meas_many()
