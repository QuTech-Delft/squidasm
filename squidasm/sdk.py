import logging
from enum import Enum, auto
from collections import namedtuple

from netqasm.sdk import NetQASMConnection
from squidasm.queues import get_queue, Signal

Message = namedtuple("Message", ["type", "msg"])
InitNewAppMessage = namedtuple("InitNewAppMessage", ["app_id", "max_qubits"])


class MessageType(Enum):
    SUBROUTINE = auto()
    SIGNAL = auto()
    INIT_NEW_APP = auto()


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
        indented_instructions = '\n'.join(f"    {instr}" for instr in subroutine.instructions)
        self._logger.debug("Puts the next subroutine "
                           f"(netqasm_version={subroutine.netqasm_version}, app_id={subroutine.app_id}):\n"
                           f"{indented_instructions}")
        self._subroutine_queue.put(Message(type=MessageType.SUBROUTINE, msg=subroutine))
        if block:
            self._subroutine_queue.join()

    def _signal_stop(self):
        self._subroutine_queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))
