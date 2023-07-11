from abc import ABC, abstractmethod
from abc import ABCMeta
from typing import Union, List

import netsquid as ns
from dataclasses import dataclass
from netsquid.protocols import Protocol
from pydantic.decorator import Dict
from qlink_interface import (
    ReqCreateBase,
    ResError,
)
from qlink_interface.interface import ResCreate

import squidasm
from netsquid_netbuilder.yaml_loadable import YamlLoadable
from pydynaa import EventHandler, EventType, Event

LinkOpenEvent = EventType("evtLinkOpen", "A link is opened")
LinkCloseEvent = EventType("evtLinkClose", "A link is closed")


class IScheduleConfig(YamlLoadable, ABC):
    pass


@dataclass
class TimeSlot:
    node1_name: str
    node2_name: str
    start: float
    end: Union[float, None]

    def contains_node(self, node_name: str) -> bool:
        return self.node2_name == node_name or self.node1_name == node_name

    def contains_link(self, node_name_1: str, node_name_2: str) -> bool:
        if self.node2_name == node_name_1 and self.node1_name == node_name_2:
            return True
        if self.node1_name == node_name_1 and self.node2_name == node_name_2:
            return True
        return False


class IScheduleProtocol(Protocol, metaclass=ABCMeta):
    def __init__(self, links, node_id_mapping: Dict[str, int]):
        super().__init__()
        self.links = links
        self._node_id_mapping = node_id_mapping
        self._node_name_mapping = {id_: name for name, id_ in self._node_id_mapping.items()}

        self._evhandler = EventHandler(self._handle_event)
        self._ev_to_timeslot: Dict[Event, TimeSlot] = {}

    def start(self):
        super().start()
        self._wait(self._evhandler, entity=self, event_type=LinkOpenEvent)
        self._wait(self._evhandler, entity=self, event_type=LinkCloseEvent)

    def stop(self):
        super().stop()
        self._dismiss(self._evhandler, entity=self, event_type=LinkOpenEvent)
        self._dismiss(self._evhandler, entity=self, event_type=LinkCloseEvent)

    def register_timeslot(self, timeslot: TimeSlot):
        open_event = self._schedule_at(timeslot.start, LinkOpenEvent)
        self._ev_to_timeslot[open_event] = timeslot

        if timeslot.end:
            close_event = self._schedule_at(timeslot.end, LinkCloseEvent)
            self._ev_to_timeslot[close_event] = timeslot

    @abstractmethod
    def register_request(self, node_id: int, req: ReqCreateBase, create_id: int):
        pass

    @abstractmethod
    def register_result(self, node_id: int, res: ResCreate):
        pass

    @abstractmethod
    def register_error(self, node_id: int, error: ResError):
        pass

    def find_timeslot(self, node_id: int, remote_id: int):
        node_name = self._node_name_mapping[node_id]
        remote_node_name = self._node_name_mapping[remote_id]
        timeslots = [timeslot for timeslot in self.registered_timeslots if timeslot.contains_link(node_name, remote_node_name)]
        return timeslots

    @property
    def registered_timeslots(self):
        return self._ev_to_timeslot.values()

    def _handle_event(self, event):
        if event.type == LinkOpenEvent:
            self._handle_open_link_event(event)
        if event.type == LinkCloseEvent:
            self._handle_close_link_event(event)

    def _handle_open_link_event(self, event):
        timeslot = self._ev_to_timeslot[event]
        if squidasm.SUPER_HACKY_SWITCH:
            print(f"{ns.sim_time(ns.MILLISECOND)} ms open link {(timeslot.node1_name, timeslot.node2_name)}")

        link = self.links[(timeslot.node1_name, timeslot.node2_name)]
        link.open()
        self._ev_to_timeslot.pop(event)

    def _handle_close_link_event(self, event):
        timeslot = self._ev_to_timeslot[event]

        if squidasm.SUPER_HACKY_SWITCH:
            print(f"{ns.sim_time(ns.MILLISECOND)} ms close link {(timeslot.node1_name, timeslot.node2_name)}")

        link = self.links[(timeslot.node1_name, timeslot.node2_name)]
        link.close()
        self._ev_to_timeslot.pop(event)


class IScheduleBuilder(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def build(cls, network,
              participating_node_names: List[str], schedule_config: IScheduleConfig) -> IScheduleProtocol:
        pass
