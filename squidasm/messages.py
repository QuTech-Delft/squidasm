from enum import Enum, auto
from collections import namedtuple

Message = namedtuple("Message", ["type", "msg"])
InitNewAppMessage = namedtuple("InitNewAppMessage", ["app_id", "max_qubits", "circuit_rules"])
StopAppMessage = namedtuple("StopAppMessage", ["app_id"])


class MessageType(Enum):
    SUBROUTINE = auto()
    SIGNAL = auto()
    INIT_NEW_APP = auto()
    STOP_APP = auto()
