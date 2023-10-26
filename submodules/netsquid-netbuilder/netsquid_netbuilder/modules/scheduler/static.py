import itertools
import math
from typing import List

import netsquid as ns
from netsquid_netbuilder.modules.scheduler.interface import (
    IScheduleBuilder,
    IScheduleConfig,
    IScheduleProtocol,
    TimeSlot,
)
from netsquid_netbuilder.network import Network
from pydantic.decorator import Dict
from qlink_interface import ReqCreateBase, ResError
from qlink_interface.interface import ResCreate

from pydynaa import EventHandler


class StaticScheduleConfig(IScheduleConfig):
    time_window: float = 1_000_000  # 1 ms
    """Size of each timeslot for entanglement generation. [ns]"""
    switch_time: float = 1000  # 1 us
    """Dead time when switching links where no entanglement generation is possible. [ns]"""
    max_multiplexing: int = 1
    """Number of links that can be open at the same time"""


class StaticScheduleProtocol(IScheduleProtocol):
    CycleEndEvent = ns.pydynaa.EventType(
        "evtCycleEnd", "A full cycle of the static schedule has been completed"
    )

    MAX_REPEATS = 1000

    def __init__(
        self,
        name: str,
        params: StaticScheduleConfig,
        schema,
        links,
        node_id_mapping: Dict[str, int],
    ):
        super().__init__(name, links, node_id_mapping)
        self.params = params
        self._schema = schema

        self.full_cycle_time = len(schema) * (
            self.params.time_window + self.params.switch_time
        )
        self._populate_cycle(cycle_start_time=0)
        self._active_requests: Dict[(int, int), ReqCreateBase] = {}
        self._termination_counter = self.MAX_REPEATS
        self._evhandler = EventHandler(self._handle_event)

    def register_request(self, node_id: int, req: ReqCreateBase, create_id: int):
        self._active_requests[(node_id, create_id)] = req
        self._active_requests[(req.remote_node_id, create_id)] = req
        self._termination_counter = self.MAX_REPEATS

        if not self.find_timeslot(node_id, req.remote_node_id):
            self._populate_cycle(cycle_start_time=self.next_cycle_start)

    def register_result(self, node_id: int, res: ResCreate):
        self._termination_counter = self.MAX_REPEATS
        if (node_id, res.create_id) not in self._active_requests.keys():
            return
        self._active_requests.pop((node_id, res.create_id))

    def register_error(self, node_id: int, error: ResError):
        pass

    @property
    def next_cycle_start(self):
        current_time = ns.sim_time()
        cycle_iter = math.floor(current_time / self.full_cycle_time)
        if cycle_iter * self.full_cycle_time < current_time:
            return (cycle_iter + 1) * self.full_cycle_time
        else:
            return cycle_iter * self.full_cycle_time

    def _populate_cycle(self, cycle_start_time):
        time = cycle_start_time
        for sub_cycle in self._schema:
            for link in sub_cycle:
                timeslot = TimeSlot(
                    node1_name=link[0],
                    node2_name=link[1],
                    start=time,
                    end=time + self.params.time_window,
                )
                self.register_timeslot(timeslot)
            time += self.params.time_window + self.params.switch_time
        self._schedule_at(time, self.CycleEndEvent)

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

    @property
    def _all_queues_empty(self) -> bool:
        for link in self.links.values():
            if link.num_requests_in_queue > 0:
                return False
        return True

    def _handle_cycle_end(self):
        # Populate a new cycle if: counter not exceeded, there are still active requests and no
        if self._termination_counter > 0 and not self._all_queues_empty:
            self._termination_counter -= 1
            self._populate_cycle(self.next_cycle_start)


class StaticScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(
        cls,
        name: str,
        network: Network,
        participating_node_names: List[str],
        schedule_config: StaticScheduleConfig,
    ) -> StaticScheduleProtocol:

        if isinstance(schedule_config, dict):
            schedule_config = StaticScheduleConfig(**schedule_config)

        link_combinations = list(itertools.permutations(participating_node_names, 2))
        links = {
            (node_1, node_2): network.links[(node_1, node_2)]
            for node_1, node_2 in link_combinations
        }

        schema = cls.generate_schema(
            link_combinations, schedule_config.max_multiplexing
        )

        scheduler = StaticScheduleProtocol(
            name, schedule_config, schema, links, network.node_name_id_mapping
        )
        return scheduler

    @staticmethod
    def generate_schema(conn: (str, str), num_conn_max_active: int):
        num_conn = len(conn)
        schema = []
        used_connections = set()  # Keep track of connections that have been used
        while len(used_connections) < num_conn:
            subcycle = []
            used_nodes = (
                set()
            )  # Keep track of nodes that have been used within the current sub-cycle
            for i in range(min(num_conn_max_active, num_conn - len(used_connections))):
                for j in range(num_conn):
                    connection = conn[j]
                    node_a, node_b = connection
                    if (
                        connection not in used_connections
                        and node_a not in used_nodes
                        and node_b not in used_nodes
                    ):
                        subcycle.append(connection)
                        used_connections.add(connection)
                        used_nodes.add(node_a)
                        used_nodes.add(node_b)
                        break
            schema.append(subcycle)
        return schema
