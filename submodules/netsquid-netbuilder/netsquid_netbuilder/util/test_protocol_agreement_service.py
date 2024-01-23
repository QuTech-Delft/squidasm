from typing import Generator, List, Union

import netsquid as ns
from netsquid_driver.entanglement_agreement_service import (
    EntanglementAgreementService,
    ReqEntanglementAgreement,
    ReqEntanglementAgreementAbort,
    ResEntanglementAgreementReached,
    ResEntanglementAgreementRejected,
)
from netsquid_netbuilder.network import ProtocolContext
from netsquid_netbuilder.protocol_base import BlueprintProtocol

from pydynaa import EventExpression


class AgreementServiceResultRegistration:
    def __init__(self):
        self.submit_agreement: List[(float, str, ReqEntanglementAgreement)] = []
        self.submit_abort: List[(float, str, ReqEntanglementAgreementAbort)] = []
        self.rec_agreement: List[(float, str, ResEntanglementAgreementReached)] = []
        self.rec_abort: List[(float, str, ResEntanglementAgreementRejected)] = []


class AgreementServiceTestProtocol(BlueprintProtocol):
    def __init__(
        self,
        peer: str,
        result_reg: AgreementServiceResultRegistration,
        requests: List[Union[ReqEntanglementAgreement, ReqEntanglementAgreementAbort]],
        send_times: List[float],
        termination_delay: float,
    ):
        super().__init__()
        self.peer = peer
        self.result_reg = result_reg
        self.requests = requests
        self.send_times = send_times
        self.listener_protocol = AgreementServiceTestProtocol.AgreementListener(
            result_reg
        )
        self.termination_delay = termination_delay
        self.add_subprotocol(self.listener_protocol)

    def set_context(self, context: ProtocolContext):
        super().set_context(context)
        self.listener_protocol.set_context(context)

    def start(self):
        super().start()
        self.listener_protocol.start()

    def stop(self):
        super().stop()
        self.listener_protocol.stop()

    def run(self) -> Generator[EventExpression, None, None]:
        node = self.context.node
        agreement_service = node.driver[EntanglementAgreementService]

        assert len(self.requests) == len(self.send_times)
        for send_time, request in zip(self.send_times, self.requests):
            yield self.await_timer(end_time=send_time)
            agreement_service.put(request)
            if isinstance(request, ReqEntanglementAgreementAbort):
                self.result_reg.submit_abort.append((ns.sim_time(), node.name, request))
            elif isinstance(request, ReqEntanglementAgreement):
                self.result_reg.submit_agreement.append(
                    (ns.sim_time(), node.name, request)
                )
            else:
                raise RuntimeError("Received incorrect request.")

        # Avoids early termination and early shutdown of AgreementListener
        yield self.await_timer(duration=self.termination_delay)

    class AgreementListener(BlueprintProtocol):
        def __init__(self, result_reg: AgreementServiceResultRegistration):
            super().__init__()
            self.result_reg = result_reg

        def run(self):
            node = self.context.node
            agreement_service = node.driver[EntanglementAgreementService]

            evt_rejected = self.await_signal(
                sender=agreement_service,
                signal_label=ResEntanglementAgreementRejected.__name__,
            )
            evt_agreement_reached = self.await_signal(
                sender=agreement_service,
                signal_label=ResEntanglementAgreementReached.__name__,
            )
            while True:
                evt_expr = yield evt_agreement_reached | evt_rejected
                [evt] = evt_expr.triggered_events
                res = agreement_service.get_signal_by_event(evt).result

                if isinstance(res, ResEntanglementAgreementRejected):
                    self.result_reg.rec_abort.append((ns.sim_time(), node.name, res))
                elif isinstance(res, ResEntanglementAgreementReached):
                    self.result_reg.rec_agreement.append(
                        (ns.sim_time(), node.name, res)
                    )
                else:
                    raise RuntimeError("Received unexpected signal.")
