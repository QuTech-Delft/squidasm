from time import sleep
import logging
from threading import Thread

from squidasm.queues import get_queue, Signal
from squidasm.network_setup import get_node
from squidasm.qnodeos import SubroutineHandler
from squidasm.backend import Backend


class SimpleCommunicator:
    def __init__(self, node_name, subroutine):
        self._subroutine = subroutine
        self._node_name = node_name
        self._subroutine_queue = get_queue(node_name)

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self._node_name})")

    def run(self, num_times=1):
        for _ in range(num_times):
            self._submit_subroutine()
        self._signal_stop()

    def _submit_subroutine(self):
        self._logger.debug(f"SimpleCommunicator for node {self._node_name} puts the next subroutine")
        self._subroutine_queue.put(self._subroutine)

    def _signal_stop(self):
        self._subroutine_queue.put(Signal.STOP)


def test():
    logging.basicConfig(level=logging.DEBUG)
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

    def run_backend():
        logging.debug("Starting backend thread")
        backend = Backend(["Alice", "Bob"])
        backend.start()
        logging.debug("End backend thread")

    app_functions = [run_alice, run_bob]
    backend_function = run_backend

    # Start the application threads
    app_threads = []
    for app_function in app_functions:
        thread = Thread(target=app_function)
        thread.start()
        app_threads.append(thread)

    # Start the backend thread
    backend_thread = Thread(target=backend_function)
    backend_thread.start()

    # Join the application threads (not the backend, since it will run forever)
    for app_thread in app_threads:
        app_thread.join()


if __name__ == '__main__':
    test()
