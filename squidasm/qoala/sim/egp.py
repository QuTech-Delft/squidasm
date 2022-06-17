from abc import ABCMeta, abstractmethod

from netsquid import BellIndex
from netsquid.protocols import ServiceProtocol
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


class EgpProtocol(EGPService):
    def __init__(self, node, magic_link_layer_protocol, name=None):
        super().__init__(node=node, name=name)
        self._ll_prot = magic_link_layer_protocol

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
        return self._ll_prot.put_from(self.node.ID, req)

    def measure_directly(self, req):
        super().measure_directly(req)
        return self._ll_prot.put_from(self.node.ID, req)

    def remote_state_preparation(self, req):
        super().remote_state_preparation(req)
        return self._ll_prot.put_from(self.node.ID, req)

    def receive(self, req):
        super().receive(req)
        self._ll_prot.put_from(self.node.ID, req)

    def stop_receive(self, req):
        super().stop_receive(req)
        self._ll_prot.put_from(self.node.ID, req)


class EgpTranslationUnit(TranslationUnit):
    def request_to_parameters(self, request, **fixed_parameters):
        return {}
