import logging

from netqasm.sdk import NetQASMConnection
from squidasm.queues import get_queue, Signal
from squidasm.backend import get_current_node_ids
from squidasm.messages import Message, InitNewAppMessage, MessageType


class NetSquidConnection(NetQASMConnection):
    def __init__(self, name, app_id=None, max_qubits=5):
        self._subroutine_queue = get_queue(name)
        super().__init__(name=name, app_id=app_id, max_qubits=max_qubits)
        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._subroutine_queue.put(Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=self._appID,
                max_qubits=max_qubits,
            ),
        ))

    def commit(self, subroutine, block=True):
        self._submit_subroutine(subroutine, block=block)

    def close(self, release_qubits=True):
        super().close(release_qubits=release_qubits)
        self._signal_stop()

    def _submit_subroutine(self, subroutine, block=True):
        self._logger.debug(f"Puts the next subroutine:\n{subroutine}")
        self._subroutine_queue.put(Message(type=MessageType.SUBROUTINE, msg=subroutine))
        if block:
            self._subroutine_queue.join()

    def _signal_stop(self):
        self._subroutine_queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))

    def _get_remote_node_id(self, node_name):
        current_node_ids = get_current_node_ids()
        node_id = current_node_ids.get(node_name)
        if node_id is None:
            raise ValueError("Unknown node with name {node_name}")
        return node_id
