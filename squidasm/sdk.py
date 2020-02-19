import logging
from threading import Thread

from netqasm.sdk import NetQASMConnection, Qubit
from squidasm.queues import get_queue, Signal
from squidasm.backend import Backend


class NetSquidConnection(NetQASMConnection):
    def __init__(self, name, app_id=None):
        super().__init__(name=name, app_id=app_id)
        self._subroutine_queue = get_queue(name)
        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    def commit(self, subroutine, block=True):
        self._submit_subroutine(subroutine, block=block)

    def close(self, release_qubits=True):
        super().close(release_qubits=release_qubits)
        self._signal_stop()

    def _submit_subroutine(self, subroutine, block=True):
        indented_instructions = '\n'.join(f"    {instr}" for instr in subroutine.instructions)
        self._logger.debug("Puts the next subroutine "
                           f"(netqasm_version={subroutine.netqasm_version}, app_id={subroutine.app_id}):\n"
                           f"{indented_instructions}")
        self._subroutine_queue.put(subroutine)
        if block:
            self._subroutine_queue.join()

    def _signal_stop(self):
        self._subroutine_queue.put(Signal.STOP)


def _test_two_nodes():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        logging.debug("Starting Alice thread")
        with NetSquidConnection("Alice") as alice:
            q1 = Qubit(alice)
            q2 = Qubit(alice)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        logging.debug("End Alice thread")

    def run_bob():
        logging.debug("Starting Bob thread")
        with NetSquidConnection("Bob") as bob:
            q1 = Qubit(bob)
            q2 = Qubit(bob)
            q1.H()
            q2.X()
            q1.X()
            q2.H()
        logging.debug("End Bob thread")

    def run_backend():
        logging.debug("Starting backend thread")
        backend = Backend(["Alice", "Bob"])
        backend.start()
        logging.debug("End backend thread")

    run_applications({
        "Alice": run_alice,
        "Bob": run_bob,
    })


def run_applications(applications):
    """Executes functions containing application scripts,

    Parameters
    ----------
    applications : dict
        Keys should be names of nodes
        Values should be the functions
    """
    node_names = list(applications.keys())
    app_functions = list(applications.values())

    def run_backend():
        logging.debug(f"Starting netsquid backend thread with nodes {node_names}")
        backend = Backend(node_names)
        backend.start()
        logging.debug("End backend thread")

    # Start the application threads
    app_threads = []
    for app_function in app_functions:
        thread = Thread(target=app_function)
        thread.start()
        app_threads.append(thread)

    # Start the backend thread
    backend_thread = Thread(target=run_backend)
    backend_thread.start()

    # Join the application threads (not the backend, since it will run forever)
    for app_thread in app_threads:
        app_thread.join()


def test_measure():
    logging.basicConfig(level=logging.DEBUG)

    def run_alice():
        with NetSquidConnection("Alice") as alice:
            q = Qubit(alice)
            q.H()
            m = q.measure()
            alice.flush()
            print(m)

    run_applications({
        "Alice": run_alice,
    })

    assert False


if __name__ == '__main__':
    test_measure()
