import itertools
from typing import List

from netsquid_netbuilder.modules.scheduler.fifo import (
    FIFOScheduleConfig,
    FIFOScheduleProtocol,
)
from netsquid_netbuilder.modules.scheduler.interface import IScheduleBuilder
from netsquid_netbuilder.network import Network
from qlink_interface import ResError


class ExampleNewScheduleConfig(FIFOScheduleConfig):
    error_print_msg: str


class ExampleNewScheduleProtocol(FIFOScheduleProtocol):
    """Part of example showing how to create a new protocol"""

    def register_error(self, node_id: int, error: ResError):
        assert isinstance(self.params, ExampleNewScheduleProtocol)
        print(f"{self.params.error_print_msg}")


class ExampleNewScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(
        cls,
        name: str,
        network: Network,
        participating_node_names: List[str],
        schedule_config: FIFOScheduleConfig,
    ) -> ExampleNewScheduleProtocol:

        if isinstance(schedule_config, dict):
            schedule_config = FIFOScheduleConfig(**schedule_config)

        link_combinations = list(itertools.permutations(participating_node_names, 2))
        links = {
            (node_1, node_2): network.links[(node_1, node_2)]
            for node_1, node_2 in link_combinations
        }

        scheduler = ExampleNewScheduleProtocol(
            name, schedule_config, links, network.node_name_id_mapping
        )
        return scheduler
