import itertools
from dataclasses import dataclass
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


@dataclass
class QueItem:
    node_id: int
    req: ReqCreateBase
    create_id: int


class FIFOScheduleConfig(IScheduleConfig):
    switch_time: float = 1000  # 1 us
    """Dead time when switching links where no entanglement generation is possible. [ns]"""
    max_multiplexing: int = 1
    """Number of links that can be open at the same time"""


class FIFOScheduleProtocol(IScheduleProtocol):
    # TODO FIFO schedule will still close the link even when next request is for same link
    # TODO FIFO schedule has nothing to prevent two links to the same node being open at the same time

    def __init__(
        self,
        name: str,
        params: FIFOScheduleConfig,
        links,
        node_id_mapping: Dict[str, int],
    ):
        super().__init__(name, links, node_id_mapping)
        self.params = params
        self._que: List[QueItem] = []
        # We need a reference item for each node per request,
        # to ensure behaviour that we don't close the connection before all nodes received their qubits
        self._per_node_ref_per_active_request: Dict[(int, int), ReqCreateBase] = {}

    def register_request(self, node_id: int, req: ReqCreateBase, create_id: int):
        # Each active request has two references
        if (
            len(self._per_node_ref_per_active_request) / 2
            < self.params.max_multiplexing
        ):
            self._activate_request(node_id, req, create_id)
        else:
            self._que.append(QueItem(node_id, req, create_id))

    def register_result(self, node_id: int, res: ResCreate):
        if (node_id, res.create_id) not in self._per_node_ref_per_active_request.keys():
            return
        self._per_node_ref_per_active_request.pop((node_id, res.create_id))

        if (
            res.remote_node_id,
            res.create_id,
        ) not in self._per_node_ref_per_active_request.keys():
            node_name = self._node_name_mapping[node_id]
            remote_node_name = self._node_name_mapping[res.remote_node_id]
            self._close_link(node_name, remote_node_name)

            if len(self._que) > 0:
                que_item = self._que.pop(0)
                self._activate_request(
                    que_item.node_id, que_item.req, que_item.create_id
                )

    def register_error(self, node_id: int, error: ResError):
        pass

    def _activate_request(self, node_id: int, req: ReqCreateBase, create_id: int):
        self._per_node_ref_per_active_request[(node_id, create_id)] = req
        self._per_node_ref_per_active_request[(req.remote_node_id, create_id)] = req
        node_name = self._node_name_mapping[node_id]
        remote_node_name = self._node_name_mapping[req.remote_node_id]
        timeslot = TimeSlot(
            node_name,
            remote_node_name,
            start=ns.sim_time() + self.params.switch_time,
            end=None,
        )
        self.register_timeslot(timeslot)


class FIFOScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(
        cls,
        name: str,
        network: Network,
        participating_node_names: List[str],
        schedule_config: FIFOScheduleConfig,
    ) -> FIFOScheduleProtocol:

        if isinstance(schedule_config, dict):
            schedule_config = FIFOScheduleConfig(**schedule_config)

        link_combinations = list(itertools.permutations(participating_node_names, 2))
        links = {
            (node_1, node_2): network.links[(node_1, node_2)]
            for node_1, node_2 in link_combinations
        }

        scheduler = FIFOScheduleProtocol(
            name, schedule_config, links, network.node_name_id_mapping
        )
        return scheduler
