from abc import ABCMeta, abstractmethod
from typing import Dict
import squidasm

import netsquid as ns
from netsquid import BellIndex
from netsquid.protocols import ServiceProtocol, NodeProtocol, Signals
from netsquid_magic.link_layer import TranslationUnit, MagicLinkLayerProtocolWithSignaling
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
from qlink_interface.interface import ResCreate

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
    def __init__(self, node, magic_link_layer_protocol: MagicLinkLayerProtocolWithSignaling, name=None):
        super().__init__(node=node, name=name)
        self._ll_prot: MagicLinkLayerProtocolWithSignaling = magic_link_layer_protocol
        self._create_id_to_request: Dict[int, ReqCreateBase] = {}

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
                if isinstance(result.msg, ResError):
                    self._handle_error(result.msg)
                else:
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
                    if isinstance(result, ResCreate):
                        self._create_id_to_request.pop(result.create_id)
                    if self._ll_prot.scheduler:
                        self._ll_prot.scheduler.register_result(self.node.ID, result.msg)

    def create_and_keep(self, req):
        super().create_and_keep(req)
        create_id = self._ll_prot.put_from(self.node.ID, req)
        if self._ll_prot.scheduler:
            self._ll_prot.scheduler.register_request(self.node.ID, req, create_id)
        self._create_id_to_request[create_id] = req

    def measure_directly(self, req):
        super().measure_directly(req)
        create_id = self._ll_prot.put_from(self.node.ID, req)
        if self._ll_prot.scheduler:
            self._ll_prot.scheduler.register_request(self.node.ID, req, create_id)
        self._create_id_to_request[create_id] = req

    def remote_state_preparation(self, req):
        super().remote_state_preparation(req)
        self._ll_prot.put_from(self.node.ID, req)

    def receive(self, req):
        super().receive(req)
        self._ll_prot.put_from(self.node.ID, req)

    def stop_receive(self, req):
        super().stop_receive(req)
        self._ll_prot.put_from(self.node.ID, req)

    def _handle_error(self, error: ResError):
        create_id = error.create_id
        if error.error_code.TIMEOUT:
            if squidasm.SUPER_HACKY_SWITCH:
                print(f"{ns.sim_time(ns.MILLISECOND)} ms Request to create entanglement "
                      f"(id:{create_id}) from {self.node.name} was terminated, restarting")
            req = self._create_id_to_request[create_id]
            new_create_id = self._ll_prot.put_from(self.node.ID, req)
            # TODO must remove old request to avoid memory build up, but get errors if I do that
            # self._create_id_to_request.pop(create_id)
            self._create_id_to_request[new_create_id] = req
            if self._ll_prot.scheduler:
                self._ll_prot.scheduler.register_error(self.node.ID, error)

            if self._ll_prot.scheduler:
                self._ll_prot.scheduler.register_request(self.node.ID, req, new_create_id)


class EgpTranslationUnit(TranslationUnit):
    def request_to_parameters(self, request, **fixed_parameters):
        return {}







