from abc import ABCMeta, abstractmethod

import netsquid as ns
from netsquid import BellIndex
from netsquid.protocols import ServiceProtocol, NodeProtocol, Signals
from netsquid_magic.link_layer import TranslationUnit
from blueprint.scheduler.interface import IScheduleProtocol, ResScheduleSlot
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

# (Mostly) copied from the nlblueprint repo.
# This is done to not have nlblueprint as a dependency.


class EGPService(ServiceProtocol, metaclass=ABCMeta):
    def __init__(self, node, name=None):
        super().__init__(node=node, name=name)
        self.register_request(ReqCreateAndKeep, self.create_and_keep)
        self.register_request(ReqMeasureDirectly, self.measure_directly)
        self.register_request(ReqReceive, self.receive)
        self.register_request(ReqStopReceive, self.stop_receive)
        self.register_response(ResCreateAndKeep)
        self.register_response(ResMeasureDirectly)
        self.register_response(ResRemoteStatePrep)
        self.register_response(ResError)
        self._current_create_id = 0

    @abstractmethod
    def create_and_keep(self, req):
        assert isinstance(req, ReqCreateAndKeep)

    @abstractmethod
    def measure_directly(self, req):
        assert isinstance(req, ReqMeasureDirectly)

    @abstractmethod
    def remote_state_preparation(self, req):
        assert isinstance(req, ReqRemoteStatePrep)

    @abstractmethod
    def receive(self, req):
        assert isinstance(req, ReqReceive)

    @abstractmethod
    def stop_receive(self, req):
        assert isinstance(req, ReqStopReceive)

    def _get_create_id(self):
        create_id = self._current_create_id
        self._current_create_id += 1
        return create_id

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()


class EgpProtocol(EGPService):
    def __init__(self, node, magic_link_layer_protocol,
                 scheduler: IScheduleProtocol, name=None):
        super().__init__(node=node, name=name)
        self._ll_prot = magic_link_layer_protocol
        self.scheduler = scheduler

    def run(self):
        while True:
            yield self.await_signal(
                sender=self._ll_prot,
                signal_label="react_to_{}".format(self.node.ID),
            )
            result = self._ll_prot.get_signal_result(
                label="react_to_{}".format(self.node.ID), receiver=self
            )
            if result.node_id == self.node.ID:
                try:
                    BellIndex(result.msg.bell_state)
                except AttributeError:
                    pass
                except ValueError:
                    raise TypeError(
                        f"{result.msg.bell_state}, which was obtained from magic link layer protocol,"
                        f"is not a :class:`netsquid.qubits.ketstates.BellIndex`."
                    )
                self.send_response(response=result.msg)

    def create_and_keep(self, req):
        super().create_and_keep(req)
        protocol = EGPRequestProtocol(self.node, req, self._ll_prot, self.scheduler)
        protocol.start()

    def measure_directly(self, req):
        super().measure_directly(req)
        protocol = EGPRequestProtocol(self.node, req, self._ll_prot, self.scheduler)
        protocol.start()

    def remote_state_preparation(self, req):
        super().remote_state_preparation(req)
        protocol = EGPRequestProtocol(self.node, req, self._ll_prot, self.scheduler)
        protocol.start()

    def receive(self, req):
        super().receive(req)
        self._ll_prot.put_from(self.node.ID, req)

    def stop_receive(self, req):
        super().stop_receive(req)
        self._ll_prot.put_from(self.node.ID, req)


class EgpTranslationUnit(TranslationUnit):
    def request_to_parameters(self, request, **fixed_parameters):
        return {}


class EGPRequestProtocol(NodeProtocol):
    def __init__(self, node, request,
                 ll_prot,
                 scheduler: IScheduleProtocol, name=None):
        super().__init__(node=node, name=name)
        self.request = request
        self.scheduler = scheduler
        self._ll_prot = ll_prot
        self.add_signal(ResScheduleSlot.__name__)

    def run(self):
        req_id = self.scheduler.schedule(self.request)
        # TODO make make signal with signal labels
        event_expr = yield self.await_signal(self.scheduler, signal_label=ResScheduleSlot.__name__)
        schedule_slot: ResScheduleSlot = self.scheduler.timeslot(req_id)
        # schedule_slot: ResScheduleSlot = self.scheduler.get_signal_result(ResScheduleSlot.__name__)
        time_until_start = schedule_slot.start - ns.sim_time()

        if time_until_start > 0:
            yield self.await_timer(time_until_start)

        self._ll_prot.put_from(self.node.ID, self.request)




