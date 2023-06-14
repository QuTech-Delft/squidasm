import itertools
from typing import Any, List

from dataclasses import dataclass
from pydantic.decorator import Dict
import numpy as np
import netsquid as ns

from blueprint.network import Network
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import TranslationUnit, MagicLinkLayerProtocol
from qlink_interface import (
    ReqCreateBase,
    ReqCreateAndKeep,
    ReqMeasureDirectly,
    ReqReceive,
    ReqRemoteStatePrep,
    ReqStopReceive,
    ResCreateAndKeep,
    ResError,
    ResMeasureDirectly,
    ResRemoteStatePrep,
)
import netsquid as ns
from blueprint.scheduler.interface import TimeSlot, IScheduleProtocol, IScheduleBuilder
from pydynaa import EventHandler, EventType, Event


@dataclass
class StaticScheduleParams:
    time_window: float = 1_000_000  # 1 ms
    switch_time: float = 100
    max_multiplexing: int = 1


class StaticScheduleProtocol(IScheduleProtocol):
    LinkOpenEvent = EventType("evtLinkOpen", "A link is opened")
    LinkCloseEvent = EventType("evtLinkClose", "A link is closed")

    def __init__(self, params: StaticScheduleParams, node_ids: List[str],
                 links):
        super().__init__()
        self.params = params
        self.num_participants = len(node_ids)
        self.links = links
        self._temp_counter = 10

        link_combinations = list(itertools.combinations(node_ids, 2))
        schema = self.generate_schema(link_combinations, params.max_multiplexing)

        self._evhandler = EventHandler(self._handle_event)
        self._ev_to_timeslot: Dict[Event, TimeSlot] = {}

        #self.link_to_id = {x[1]: x[0] for x in enumerate(link_combinations)}

        self.full_cycle_time = len(schema) * (self.params.time_window + self.params.switch_time)
        time = 0
        for sub_cycle in schema:
            for link in sub_cycle:
                timeslot = TimeSlot(node1_name=link[0], node2_name=link[1],
                                    start=time, end=time + self.params.time_window)
                self._register_timeslot(timeslot)
            time += self.params.time_window + self.params.switch_time

    def start(self):
        self._wait(self._evhandler, entity=self, event_type=self.LinkOpenEvent)
        self._wait(self._evhandler, entity=self, event_type=self.LinkCloseEvent)

    def stop(self):
        self._dismiss(self._evhandler, entity=self, event_type=self.LinkOpenEvent)
        self._dismiss(self._evhandler, entity=self, event_type=self.LinkCloseEvent)

    @staticmethod
    def generate_schema(conn, num_conn_max_active):
        num_conn = len(conn)
        schema = []
        used_connections = set()  # Keep track of connections that have been used
        while len(used_connections) < num_conn:
            subcycle = []
            used_nodes = set()  # Keep track of nodes that have been used within the current sub-cycle
            for i in range(min(num_conn_max_active, num_conn - len(used_connections))):
                for j in range(num_conn):
                    connection = conn[j]
                    node_a, node_b = connection
                    if connection not in used_connections and node_a not in used_nodes and node_b not in used_nodes:
                        subcycle.append(connection)
                        used_connections.add(connection)
                        used_nodes.add(node_a)
                        used_nodes.add(node_b)
                        break
            schema.append(subcycle)
        return schema

    def _register_timeslot(self, timeslot: TimeSlot):
        open_event = self._schedule_at(timeslot.start, self.LinkOpenEvent)
        close_event = self._schedule_at(timeslot.end, self.LinkCloseEvent)

        self._ev_to_timeslot[open_event] = timeslot
        self._ev_to_timeslot[close_event] = timeslot

    def _handle_event(self, event):
        if event.type == self.LinkOpenEvent:
            timeslot = self._ev_to_timeslot[event]
            self.open_link(timeslot)
            self._ev_to_timeslot.pop(event)
        if event.type == self.LinkCloseEvent:
            timeslot = self._ev_to_timeslot[event]
            self.close_link(timeslot)
            self._ev_to_timeslot.pop(event)

    def open_link(self, timeslot: TimeSlot):
        print(f"{ns.sim_time()} open link {(timeslot.node1_name, timeslot.node2_name)}")

        link = self.links[(timeslot.node1_name, timeslot.node2_name)]
        link.open()
        new_timeslot = TimeSlot(timeslot.node1_name, timeslot.node2_name,
                                start=timeslot.start+self.full_cycle_time,
                                end=timeslot.end+self.full_cycle_time)
        if self._temp_counter > 0:
            self._register_timeslot(new_timeslot)
            self._temp_counter -= 1

    def close_link(self, timeslot: TimeSlot):
        print(f"{ns.sim_time()} close link {(timeslot.node1_name, timeslot.node2_name)}")

        link = self.links[(timeslot.node1_name, timeslot.node2_name)]
        link.close()


class StaticScheduleBuilder:
    @classmethod
    def build(cls, links) -> StaticScheduleProtocol:
        params = StaticScheduleParams()
        name_1_temp = [x[0] for x in links.keys()]
        name_2_temp = [x[1] for x in links.keys()]
        node_names = list(set(name_1_temp + name_2_temp))
        scheduler = StaticScheduleProtocol(params, node_names, links)
        return scheduler

