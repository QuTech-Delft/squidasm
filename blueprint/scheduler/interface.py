from abc import ABCMeta, abstractmethod
from typing import Any, Optional, List

from dataclasses import dataclass
from pydantic.decorator import Dict

#from blueprint.network import Network
from netsquid.protocols import Protocol

from netsquid_magic.link_layer import MagicLinkLayerProtocol


@dataclass
class TimeSlot:
    node1_name: str
    node2_name: str
    start: float
    end: float


class IScheduleProtocol(Protocol, metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        #self.add_signal(ResScheduleSlot.__name__)
        self._timeslots: List[TimeSlot] = []

    def timeslot(self, node_id) -> List[TimeSlot]:
        return list(filter(lambda x: x.node1_name is node_id or x.node2_name is node_id, self._timeslots))

    def start(self):
        super().start()

    def stop(self):
        super().stop()


class IScheduleBuilder(metaclass=ABCMeta):
    @abstractmethod
    def build(self):
        pass
