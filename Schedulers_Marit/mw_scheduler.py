import itertools
import math
from dataclasses import dataclass
from typing import List

import netsquid as ns
from netsquid_netbuilder.modules.scheduler.interface import (
    IScheduleBuilder,
    IScheduleConfig,
    IScheduleProtocol,
    TimeSlot,
)
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.network import Network
from pydantic.decorator import Dict
from qlink_interface import ReqCreateBase, ResError
from qlink_interface.interface import ResCreate

from pydynaa import Event, EventHandler, EventType


@dataclass
class QueItem:
    node_id: int
    req: ReqCreateBase
    create_id: int


class MaxWeightScheduleConfig(IScheduleConfig):
    time_window: float = 1_000_000_000
    """Size of each timeslot for entanglement generation. [ns]"""
    switch_time: float = 1000
    """Dead time when switching links where no entanglement generation is possible. [ns]"""
    max_multiplexing: int = 1
    """Number of links that can be open at the same time"""


class MaxWeightScheduleProtocol(IScheduleProtocol):

    CycleEndEvent = ns.pydynaa.EventType("evtCycleEnd", "A full cycle of the static schedule has been completed")    
    MAX_REPEATS = 10000

    def __init__(
        self,
        name: str,
        params: MaxWeightScheduleConfig,
        links,
        node_id_mapping: Dict[str, int],
    ):
        super().__init__(name, links, node_id_mapping)
        self.params = params
        self._que: Dict[(int, int),[QueItem]] = {}
        self._per_node_ref_per_active_request: Dict[(int, int), ReqCreateBase] = {}

        self.links_is_open = {}
        self.full_cycle_time = self.params.time_window + self.params.switch_time
        self._populate_cycle(self.full_cycle_time)
        self._termination_counter = self.MAX_REPEATS
        self._evhandler = EventHandler(self._handle_event)
        self._logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self.name})"
        )

        self._logger.info(f"MAX_REPEATS = {self.MAX_REPEATS}")


    def register_request(self, node_id: int, req: ReqCreateBase, create_id: int):

        # NOTE: lower number of nodes is always first
        if (node_id, req.remote_node_id) not in self._que.keys():
            self._que[(node_id, req.remote_node_id)] = []
        self._que[(node_id, req.remote_node_id)].append(QueItem(node_id, req, create_id))

    def register_result(self, node_id: int, res: ResCreate):
        
        if (node_id, res.create_id) not in self._per_node_ref_per_active_request.keys():
            return
        self._per_node_ref_per_active_request.pop((node_id, res.create_id))

        if (node_id, res.remote_node_id) in self._que and len(self._que[(node_id, res.remote_node_id)]) > 0:
            node_name = self._node_name_mapping[node_id]
            remote_node_name = self._node_name_mapping[res.remote_node_id]
            self._close_link(node_name, remote_node_name)
            
            self._que[(node_id, res.remote_node_id)].pop(0)
        
    def register_error(self, node_id: int, error: ResError):
        pass

    def _activate_request(self, node_id: int, req: ReqCreateBase, create_id: int, time: float):

        self._per_node_ref_per_active_request[(node_id, create_id)] = req
        self._per_node_ref_per_active_request[(req.remote_node_id, create_id)] = req

        node_name = self._node_name_mapping[node_id]
        remote_node_name = self._node_name_mapping[req.remote_node_id]

        timeslot = TimeSlot(
            node_name,
            remote_node_name,
            start=time,
            end=time + self.params.time_window,
        )
        self.register_timeslot(timeslot)
        
    @property
    def next_cycle_start(self):
        current_time = ns.sim_time()
        cycle_iter = math.floor(current_time / self.full_cycle_time)
        if cycle_iter * self.full_cycle_time < current_time:
            return (cycle_iter + 1) * self.full_cycle_time
        else:
            return cycle_iter * self.full_cycle_time

    def _populate_cycle(self, time):

        self._schedule_at(time+self.full_cycle_time, self.CycleEndEvent)

        # select the queue items to be executed in the next timeslot
        que_items = []
        used_nodes = []
        for i in range(0, self.params.max_multiplexing):
            max_val = 0
            next_item_key = None
            next_item_val = None
            for key, value in self._que.items():
                if len(value) > max_val and (key[0] and key[1]) not in used_nodes:
                    next_item_key = key
                    next_item_val = self._que[key][0]
                    max_val = len(value)
            if max_val > 0:
                que_items.append(next_item_val)
                used_nodes.extend(next_item_key)
        for que_item in que_items:
            self._activate_request(que_item.node_id, que_item.req, que_item.create_id, time)
        
    def start(self):
        super().start()
        self._wait(self._evhandler, entity=self, event_type=self.CycleEndEvent)

    def stop(self):
        super().stop()
        self._dismiss(self._evhandler, entity=self, event_type=self.CycleEndEvent)

    def _handle_event(self, event):
        super()._handle_event(event)
        if event.type == self.CycleEndEvent:
            self._handle_cycle_end()

    def _handle_cycle_end(self):
        # Populate a new cycle if: counter not exceeded, there are still active requests and no
        if self._termination_counter > 0:
            for key, value in self._que.items():
                # if there are still requests in the queue
                if len(self._que[key]) > 0:
                    self._termination_counter -= 1
                    self._populate_cycle(self.next_cycle_start)
                    return
            self._logger.info(f"PROTOCOL END")
        else:
            self._logger.info(f"MAX_REPEATS REACHED")

    def _open_link(self, node1_name: str, node2_name: str):
        self._logger.info(f"Opening link between nodes {node1_name} and {node2_name}")
        self.links[(node1_name, node2_name)].open()
        self.links_is_open[(node1_name, node2_name)] = True

    def _close_link(self, node1_name: str, node2_name: str):
        if self.links_is_open[(node1_name, node2_name)]:
            self._logger.info(f"Closing link between nodes {node1_name} and {node2_name}")
            self.links[(node1_name, node2_name)].close()
            self.links_is_open[(node1_name, node2_name)] = False


class MaxWeightScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(
        cls,
        name: str,
        network: Network,
        participating_node_names: List[str],
        schedule_config: MaxWeightScheduleConfig,
    ) -> MaxWeightScheduleProtocol:

        if isinstance(schedule_config, dict):
            schedule_config = MaxWeightScheduleConfig(**schedule_config)

        link_combinations = list(itertools.permutations(participating_node_names, 2))
        links = {
            (node_1, node_2): network.links[(node_1, node_2)]
            for node_1, node_2 in link_combinations
        }

        scheduler = MaxWeightScheduleProtocol(
            name, schedule_config, links, network.node_name_id_mapping
        )
        return scheduler