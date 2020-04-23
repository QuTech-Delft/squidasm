from netqasm.parsing import parse_text_subroutine
from netqasm.logging import get_netqasm_logger
from squidasm.queues import get_queue, Signal
from squidasm.sdk import Message, InitNewAppMessage, MessageType


class SimpleCommunicator:
    def __init__(self, node_name, subroutine, app_id=0, max_qubits=5):
        self._subroutine = parse_text_subroutine(subroutine)
        self._node_name = node_name
        self._subroutine_queue = get_queue(node_name)
        self._init_new_app(app_id=app_id, max_qubits=max_qubits)

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self._node_name})")

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
        self._logger.debug(f"SimpleCommunicator for node {self._node_name} puts the next subroutine:\n"
                           f"{self._subroutine}")
        self._subroutine_queue.put(Message(type=MessageType.SUBROUTINE, msg=bytes(self._subroutine)))

    def _signal_stop(self):
        self._subroutine_queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))
        self._subroutine_queue.join()
