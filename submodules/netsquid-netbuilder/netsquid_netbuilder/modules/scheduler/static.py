import itertools
import math
from typing import List

import netsquid as ns
from pydantic.decorator import Dict
from qlink_interface import (
    ReqCreateBase,
    ResError,
)
from qlink_interface.interface import ResCreate

from netsquid_netbuilder.modules.scheduler.interface import TimeSlot, IScheduleProtocol, \
    IScheduleBuilder, IScheduleConfig
from netsquid_netbuilder.network import Network


class StaticScheduleConfig(IScheduleConfig):
    time_window: float = 1_000_000  # 1 ms
    switch_time: float = 1000  # 1 us
    max_multiplexing: int = 1


class StaticScheduleProtocol(IScheduleProtocol):
    def __init__(self, name: str, params: StaticScheduleConfig, schema,
                 links, node_id_mapping: Dict[str, int]):
        super().__init__(name, links, node_id_mapping)
        self.params = params
        self._schema = schema

        self.full_cycle_time = len(schema) * (self.params.time_window + self.params.switch_time)
        self._populate_cycle(cycle_start_time=0)

    def register_request(self, node_id: int, req: ReqCreateBase, create_id: int):
        if not self.find_timeslot(node_id, req.remote_node_id):
            current_time = ns.sim_time()
            cycle_iter = math.floor(current_time / self.full_cycle_time)
            next_cycle_start = (cycle_iter + 1) * self.full_cycle_time
            self._populate_cycle(cycle_start_time=next_cycle_start)

    def register_result(self, node_id: int, res: ResCreate):
        pass

    def register_error(self, node_id: int, error: ResError):
        pass

    def _populate_cycle(self, cycle_start_time):
        time = cycle_start_time
        for sub_cycle in self._schema:
            for link in sub_cycle:
                timeslot = TimeSlot(node1_name=link[0], node2_name=link[1],
                                    start=time, end=time + self.params.time_window)
                self.register_timeslot(timeslot)
            time += self.params.time_window + self.params.switch_time


class StaticScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(cls, name: str, network: Network,
              participating_node_names: List[str],
              schedule_config: StaticScheduleConfig) -> StaticScheduleProtocol:

        if isinstance(schedule_config, dict):
            schedule_config = StaticScheduleConfig(**schedule_config)

        link_combinations = list(itertools.permutations(participating_node_names, 2))
        links = {(node_1, node_2): network.links[(node_1, node_2)] for node_1, node_2 in link_combinations}

        schema = cls.generate_schema(link_combinations, schedule_config.max_multiplexing)

        scheduler = StaticScheduleProtocol(name, schedule_config, schema, links, network.node_name_id_mapping)
        return scheduler

    @staticmethod
    def generate_schema(conn: (str, str), num_conn_max_active: int):
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

