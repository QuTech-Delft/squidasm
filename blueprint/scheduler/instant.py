from typing import Any

from dataclasses import dataclass
from pydantic.decorator import Dict

from blueprint.network import Network
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import TranslationUnit
from qlink_interface import (
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
from blueprint.scheduler.interface import ResScheduleSlot, IScheduleProtocol, IScheduleBuilder


class InstantScheduleProtocol(IScheduleProtocol):
    def __init__(self):
        super().__init__()

    def schedule(self, request):
        response = ResScheduleSlot(start=ns.sim_time(), end=None)
        req_id = len(self._timeslots)
        self._timeslots[req_id] = response
        self.send_signal(ResScheduleSlot.__name__, 0)
        return req_id

    def register_request_failed(self, request):
        # TODO maybe repeat with counter?
        raise Exception("TODO")


class InstantScheduleBuilder(IScheduleBuilder):
    @classmethod
    def build(cls, network: Network) -> Dict[str, InstantScheduleProtocol]:
        schedulers = {}
        for node_name in network.nodes.keys():
            schedulers[node_name] = InstantScheduleProtocol()
        return schedulers

