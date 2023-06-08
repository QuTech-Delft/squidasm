from abc import ABCMeta, abstractmethod
from typing import Any, Optional

from dataclasses import dataclass
from pydantic.decorator import Dict

#from blueprint.network import Network
from netsquid.protocols import Protocol


@dataclass
class ResScheduleSlot:
    start: float
    end: Optional[float]


class IScheduleProtocol(Protocol, metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        self.add_signal(ResScheduleSlot.__name__)
        self._timeslots: Dict[int, ResScheduleSlot] = {}

    @abstractmethod
    def schedule(self, request) -> int:
        pass

    def register_request_complete(self, request):
        self._timeslots.pop(request)

    @abstractmethod
    def register_request_failed(self, request):
        pass

    def timeslot(self, req_id):
        return self._timeslots[req_id]

    def start(self):
        super().start()

    def stop(self):
        super().stop()


class IScheduleBuilder(metaclass=ABCMeta):
    @abstractmethod
    def build(self, network) -> Dict[str, IScheduleProtocol]:
        pass
