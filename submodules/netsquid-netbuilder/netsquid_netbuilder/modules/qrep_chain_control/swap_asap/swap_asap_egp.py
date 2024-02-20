"""Implementation of a link layer protocol for a repeater chain
of automated nodes.
"""
from copy import copy
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
from collections import defaultdict

from dataclasses import dataclass

import numpy as np
import netsquid as ns
from netsquid_driver.EGP import EGPService, ResMeasureDirectly, ResCreateAndKeep
from netsquid_driver.entanglement_service import (EntanglementService, ReqEntanglement,
                                                  ResEntanglementSuccess, ResEntanglementError, ReqEntanglementAbort,
                                                  EntanglementError)
from netsquid_driver.entanglement_tracker_service import EntanglementTrackerService
from netsquid_driver.measurement_services import MeasureService, ReqMeasure, ResMeasure
from netsquid_driver.classical_routing_service import ClassicalRoutingService, RemoteServiceRequest
from qlink_interface import MeasurementBasis, ReqCreateBase, ReqCreateAndKeep, ReqMeasureDirectly, ReqReceive, ReqStopReceive, ResError, ErrorCode
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap_service import SwapASAPService, ReqSwapASAPAbort, ReqSwapASAP
from netsquid_driver.memory_manager_service import QuantumMemoryManager, ReqMove, ReqFreeMemory, \
    ResMoveSuccess

if TYPE_CHECKING:
    from netsquid_netbuilder.builder.repeater_chain import Chain


@dataclass
class ReqEGPAsk:
    qlink_create_request: ReqCreateBase
    origin_node_id: int
    create_id: int


@dataclass
class ReqEGPConfirm:
    create_id: int


@dataclass
class ReqEGPError:
    result_error: ResError
    origin_node_id: int


@dataclass
class QueueItem:
    qlink_create_request: ReqCreateBase
    create_id: int


class SwapAsapEndNodeLinkLayerProtocol(EGPService):
    """Link layer protocol for end nodes in a repeater chain of automated nodes generating end-to-end entanglement once.

    The process starts when a request is placed on one of the end nodes. This can be a
    :class:`~qlink_interface.ReqMeasureDirectly` request, if the entangled pair should be measured upon generation
    (e.g. for QKD) or a :class:`~qlink_interface.ReqCreateAndKeep` request, if the entangled pair should be kept.

    The end node who received the request then places a message on its neighbour node to be forwarded across the chain
    to the other end node, asking to generate entanglement. Upon receival of this message, the second end node sends
    a confirmation message back and starts entanglement generation with its neighbour. When the original end node gets
    the confirmation message, it sends a message through the chain to activate all (automated) repeater nodes and starts
    entanglement generation with its neighbour.

    When the end node that initiated the process receives all the swap outcomes from the repeater nodes, it sends a
    success response back, which can be :class:`~nlblueprint.services.EGP.ResMeasureDirectly` or
    :class:`~qlink_interface.ResCreateAndKeep`. In the second case, a measurement request
    :class:`~nlblueprint.services.operation_services.ReqMeasure` is placed on the local measurement service and the
    outcome of this measurement is included in the response.


    Parameters
    ----------
        node : :class:`~netsquid.nodes.node.Node`
            The node this protocol is running on
        name : str, optional
            The name of this protocol

    """

    _TYPE_CONFIRM = "confirm"
    _TYPE_ASK = "ask"

    class WaitIfMeasurementOutcomeShouldBeKept(ns.protocols.nodeprotocols.NodeProtocol):
        """Subprotocol to wait and decide whether a measurement outcome should be kept.

        Measurement outcomes on qubits should only be returned if the qubit is successfully entangled with the remote
        end node. However, in case of a measure-directly request, you want to measure your qubit straight away to avoid
        memory decoherence instead of waiting until end-to-end entanglement is heralded. This protocol then hangs
        on to the measurement result, discarding it if end-to-end entanglement generation fails and sending a response
        with the outcome if it succeeds.

        Parameters
        ----------
        superprotocol : :obj:`netsquid_qrepchain.control_layer.swapasap_egp.SwapAsapEndNodeLinkLayerProtocol`
            Protocol of which this protocol should be used as a subprotocol.
        id : int
            Identifier for the subprotocol. Used to name it.

        """
        def __init__(self, superprotocol, id):
            super().__init__(node=superprotocol.node, name=f"wait_if_measurement_outcome_should_be_kept_{id}")
            self._superprotocol = superprotocol
            self._link_identifier = None
            self._remote_node_id = None
            self.measurement_outcome = None
            self.measurement_basis = None
            self.create_id = None
            self.bell_state = None

        def start(self, link_identifier, remote_node_id, measurement_outcome, measurement_basis, create_id):
            """Start the subprotocol to hold on to a specific measurement result.

            Parameters
            ----------
            link_identifier : :obj:`entanglement_tracker_service.LinkIdentifier`
                Link identifier of qubit that was measured.
            remote_node_id : int
                Identifier of the remote end node with which entanglement is being generated.
            measurement_outcome : bool
                Outcome of the measurement.
            measurement_basis : :obj:`qlink_interface.interface.MeasurementBasis`
                The basis in which the measurement was performed.
            create_id : int
                Identifier of the request on the superprotocol for which the measurement was performed.

            """
            self._link_identifier = link_identifier
            self._remote_node_id = remote_node_id
            self.measurement_outcome = measurement_outcome
            self.measurement_basis = measurement_basis
            self.create_id = create_id
            self.bell_state = None
            super().start()

        def run(self):
            # wait until success or failure of end-to-end entanglement is heralded
            entanglement_tracker = self.node.driver[EntanglementTrackerService]
            yield from entanglement_tracker.await_entanglement(node_ids={self.node.ID,
                                                                         self._remote_node_id},
                                                               link_identifiers={self._link_identifier},
                                                               other_nodes_allowed=False)

            # if already enough pairs were generated, don't bother sending the response
            # (sending the response can be confusing in this case, as more responses are obtained than expected)
            if self._superprotocol._number_pairs_generated >= self._superprotocol._number_pairs_to_generate:
                return

            # if entanglement was successfully generated, send a response; else, do nothing.
            entanglement_info = entanglement_tracker.get_entanglement_info_of_link(self._link_identifier)
            if entanglement_info.intact:
                self.bell_state = entanglement_info.bell_index
                self._superprotocol._handle_heralded_success_for_measured_qubit(subprotocol=self)

    def __init__(self, node, node_name_id_mapping: Dict[str, int], chain, name=None):
        super().__init__(node=node, name=name)
        # actual params
        self._node_name_id_mapping = node_name_id_mapping
        self._id_node_name_mapping = {id_: node_name for node_name, id_ in node_name_id_mapping.items()}
        self._local_measurement_angles = None
        self._remote_node_name: Optional[str] = None
        self._remote_node_id: Optional[int] = None
        self._chain: Chain = chain
        self._create_id = None

        self._active_request: Optional[ReqCreateBase] = None
        self._active_request_create_id: Optional[int] = None

        # params that should be part of a "ActiveRequest" object
        self._should_keep = None
        self._is_upstream = None
        self._link_identifier = None  # link identifier of most recently generated entanglement
        self._number_pairs_to_generate = None
        self._number_pairs_generated = None
        self._handle_request_signal = "handle_request_signal"
        self.add_signal(self._handle_request_signal)
        self._rotation_to_measbasis = {(0, np.pi / 2, 0): MeasurementBasis.X,
                                       (np.pi / 2, 0, 0): MeasurementBasis.Y,
                                       (0, 0, 0): MeasurementBasis.Z}
        self._bell_state = None  # Bell index of expected end-to-end entanglement
        self._unique_id = 0
        self._sequence_number = 0
        self._measurement_subprotocols = []
        self._request_queue: List[QueueItem] = []
        self._ask_queue: List[ReqEGPAsk] = []

        # Keep track of the rules for receiving EPR pairs
        self._recv_rules = defaultdict(set)

        self.register_request(ReqEGPAsk, self._handle_ask_request)
        self.register_request(ReqEGPConfirm, self._handle_confirm)
        self.register_request(ReqEGPError, self._handle_error)

    @property
    def routing_service(self) -> ClassicalRoutingService:
        return self.node.driver.services[ClassicalRoutingService]

    def run(self):
        """Generates end-to-end entanglement across a repeater chain of automated nodes."""
        while True:
            yield self.await_signal(sender=self, signal_label=self._handle_request_signal)
            if self._should_keep:
                yield from self._execute_create_and_keep()
            else:
                yield from self._execute_measure_directly()
            if self._is_upstream:
                self._shut_down_repeater_chain()
            self._clear_active_request()
            self._attempt_start_next_request()

    def _shut_down_repeater_chain(self):
        """Send a message to the repeaters in the chain to make them stop generating and swapping entanglement.

        The repeaters have been sent a swap-asap request telling them to keep generating and swapping entanglement
        indefinitely. This method sends them a swap-asap-abort request to stop them from going on forever.

        """
        repeater_node_names = list(self._chain.repeater_nodes_dict.keys())
        req = ReqSwapASAPAbort(request_id=self._create_id)
        message = RemoteServiceRequest(req, SwapASAPService, origin=self.node.name, targets=repeater_node_names)

        self.routing_service.put(message)

    def _execute_create_and_keep(self):
        """Execute a create-and-keep request.

        End-to-end entanglement is generated and a response is sent detailing the created entangled state and
        the location of the qubit.
        """
        self._number_pairs_generated = 0
        while self._number_pairs_generated < self._number_pairs_to_generate:
            yield from self._generate_end_to_end_entanglement()
            self._number_pairs_generated += 1
            self.send_response(ResCreateAndKeep(create_id=self._create_id,
                                                bell_state=self._bell_state,
                                                logical_qubit_id=self._mem_pos_most_recent_entanglement,
                                                sequence_number=self._sequence_number))

    def _generate_end_to_end_entanglement(self):
        """Generate entanglement between this node and the other end node (specified in the request).

        End-to-end entanglement is generated by generating entanglement with this end node's neighbour,
        and then waiting for the entanglement tracker to decide that either
        1. the local entangled qubit has become entangled with the other end node, or
        2. the entangled state of the local entangled qubit has been destroyed (e.g. because a qubit has been discarded
        by a repeater node).

        In case the second condition is met, a new attempt is made by starting entanglement generation with the
        neighbour again.

        """
        while True:
            yield from self._perform_own_link_layer()
            yield from self._entanglement_tracker.await_entanglement(node_ids={self.node.ID, self._remote_node_id},
                                                                     link_identifiers={self._link_identifier},
                                                                     other_nodes_allowed=False)
            entanglement_info = self._entanglement_tracker.get_entanglement_info_of_link(self._link_identifier)
            if entanglement_info.intact:
                self._bell_state = entanglement_info.bell_index
                self._entanglement_tracker.untrack_entanglement_info(entanglement_info)
                break
            else:
                self._free_memory()

    def _execute_measure_directly(self):
        """Execute a measure-directly request.

        Generate entanglement locally and measure it as soon as a local qubit becomes available.
        The measurement result is then kept until the entanglement tracker learns whether entangling the measured
        qubit with the remote node has failed or succeeded. If it failed, the result is discarded. If it succeeded,
        a response is sent with the measurement result and the result is counted towards the completion of the
        measure-directly request.
        As soon as the local qubit has been measured, local entanglement generation will restart again,
        up until when local entanglement generation has been completed and it turns out that enough measurement results
        have been successfully reported.
        """
        self._number_pairs_generated = 0
        while self._number_pairs_generated < self._number_pairs_to_generate:
            yield from self._perform_own_link_layer()
            if self._number_pairs_generated >= self._number_pairs_to_generate:
                # if the own link layer finished because it was aborted, we don't need to measure
                break
            request = ReqMeasure(mem_pos=self._mem_pos_most_recent_entanglement,
                                 x_rotation_angle_1=self._local_measurement_angles["x_1"],
                                 y_rotation_angle=self._local_measurement_angles["y"],
                                 x_rotation_angle_2=self._local_measurement_angles["x_2"])
            measure_protocol = self.node.driver.services[MeasureService]
            measure_protocol.put(request=request)
            yield self.await_signal(sender=measure_protocol,
                                    signal_label=ResMeasure.__name__)
            response = measure_protocol.get_signal_result(label=ResMeasure.__name__, receiver=self)
            if isinstance(response.outcome, list):
                measurement_outcome = response.outcome[0]
            else:
                measurement_outcome = response.outcome
            self._wait_and_decide_if_measurement_outcome_should_be_kept(link_identifier=self._link_identifier,
                                                                        measurement_outcome=measurement_outcome)
            self._free_memory()

    def _wait_and_decide_if_measurement_outcome_should_be_kept(self, link_identifier, measurement_outcome):
        """Start a subprotocol to hold on to a measurement outcome until success or failure is heralded.

        Measurement outcomes on qubits should only be returned if the qubit is successfully entangled with the remote
        end node. However, in case of a measure-directly request, you want to measure your qubit straight away to avoid
        memory decoherence instead of waiting until end-to-end entanglement is heralded.
        This method starts a protocol that hangs on to the measurement result,
        discarding it if end-to-end entanglement generation fails,
        and sending a response with the outcome if it succeeds.

        Parameters
        ----------
        link_identifier : :obj:`entanglement_tracker_service.LinkIdentifier`
            Link identifier of qubit that was measured.
        measurement_outcome : bool
            Outcome of the measurement.

        """
        free_subprotocols = [prot for prot in self._measurement_subprotocols if not prot.is_running]
        if not free_subprotocols:
            subprotocol = self.WaitIfMeasurementOutcomeShouldBeKept(superprotocol=self,
                                                                    id=len(self._measurement_subprotocols))
            self._measurement_subprotocols.append(subprotocol)
        else:
            subprotocol = free_subprotocols[0]
        measurement_basis = self._rotation_to_measbasis[tuple(self._local_measurement_angles.values())]
        subprotocol.start(link_identifier=link_identifier, remote_node_id=self._remote_node_id,
                          measurement_outcome=measurement_outcome, measurement_basis=measurement_basis,
                          create_id=self._create_id)

    def _handle_heralded_success_for_measured_qubit(self, subprotocol):
        """Method for when a subprotocol holding on to measurement result indicates it was entangled successfully.

        Sends a measure-directly response and if enough pairs have been generated, it stops remaining running
        subprotocols and aborts local entanglement generation.

        Parameters
        ----------
        subprotocol : :obj:`netsquid_qrepchain.control_layer.swapasap_egp.SwapAsapEndNodeLinkLayerProtocol \
            .WaitIfMeasurementOutcomeShouldBeKept`
            Subprotocol that calls this method.

        Notes
        -----
        Stopping local entanglement generation with an abort request results in the loop of
        `_perform_own_link_layer()` to be broken, allowing the protocol to continue.
        No abort request is sent to the node that this node was generating entanglement with;
        entanglement generation on that node should be aborted through `_shut_down_repeater_chain()`,
        which gets triggered immediately exactly because the protocol is made to continue through the abort request.

        """
        response = ResMeasureDirectly(measurement_outcome=subprotocol.measurement_outcome,
                                      create_id=subprotocol.create_id,
                                      bell_state=subprotocol.bell_state,
                                      measurement_basis=subprotocol.measurement_basis,
                                      sequence_number=self._sequence_number)
        self.send_response(response=response)
        self._sequence_number += 1
        self._number_pairs_generated += 1
        if self._number_pairs_generated == self._number_pairs_to_generate:
            for prot in self._measurement_subprotocols:
                prot.stop()
            self.node.driver[EntanglementService].put(ReqEntanglementAbort(remote_node_name=self._remote_node_name))

    def _handle_ask_request(self, req: ReqEGPAsk):
        """Handles ask message received from remote end node."""
        if not self._is_valid_request(req.qlink_create_request, req.origin_node_id):
            result_error = ResError(
                create_id=req.create_id,
                error_code=ErrorCode.REJECTED,
            )
            self._send_error_to_other_egp(result_error, req.origin_node_id)
            return

        self._ask_queue.append(req)
        self._attempt_start_next_request()

    def _start_ask_request(self, req: ReqEGPAsk):
        """starts ask message received from remote end node."""
        self._active_request_create_id = req.create_id
        self._create_id = req.create_id
        self._is_upstream = False
        self._remote_node_id = req.origin_node_id
        self._remote_node_name = self._id_node_name_mapping[self._remote_node_id]
        # self._remote_node_name = # from ask put here
        self._send_confirm_message_to_other_egp()
        if isinstance(req.qlink_create_request, ReqCreateAndKeep):
            self._should_keep = True  # otherwise, there would have been measurement angles
        else:
            assert isinstance(req.qlink_create_request, ReqMeasureDirectly)
            self._should_keep = False
            # TODO fix setting measurement angles
            #self._local_measurement_angles = req.qlink_create_request.
        self._sequence_number = 0
        self._number_pairs_to_generate = req.qlink_create_request.number
        self.send_signal(self._handle_request_signal)

    def _handle_confirm(self, req: ReqEGPConfirm):
        """Handles confirm message received from remote end node."""
        assert req.create_id == self._active_request_create_id
        self._is_upstream = True
        self.send_repeater_activation_message()
        self._create_id = req.create_id
        self.send_signal(self._handle_request_signal)

    def _handle_error(self, req: ReqEGPError):
        """Handles error message received from remote end node."""
        assert req.result_error.create_id == self._active_request_create_id
        assert req.origin_node_id == self._remote_node_id
        self.send_response(req.result_error)
        self._clear_active_request()
        self._attempt_start_next_request()

    def _send_confirm_message_to_other_egp(self):
        """Sends a message to the other end node on the chain confirming that it wants to start generating entanglement."""
        req = ReqEGPConfirm(self._create_id)
        message = RemoteServiceRequest(req, EGPService, origin=self.node.name, targets=[self._remote_node_name])
        self.routing_service.put(message)

    def _send_ask_to_other_egp(self, req: ReqCreateBase):
        """Sends a message to the other end node on the chain asking if it wants to start generating entanglement."""
        req = ReqEGPAsk(req, self.node.ID, self._create_id)
        message = RemoteServiceRequest(req, EGPService, origin=self.node.name, targets=[self._remote_node_name])
        self.routing_service.put(message)

    def _send_error_to_other_egp(self, res: ResError, remote_node_id: int):
        req = ReqEGPError(result_error=res, origin_node_id=self.node.ID)
        remote_node_name = self._id_node_name_mapping[remote_node_id]
        message = RemoteServiceRequest(req, EGPService, origin=self.node.name, targets=[remote_node_name])
        self.routing_service.put(message)

    def create_and_keep(self, req: ReqCreateAndKeep):
        """Starts the process of generating an end-to-end entangled pair to be kept by sending message to other end node
        asking to start entanglement generation.

        Parameters
        ----------
        req : :class:`~qlink_interface.ReqCreateAndKeep`
            Request that needs to be handled by this method.

        """
        req_create_id = self._get_create_id()
        self._request_queue.append(QueueItem(req, req_create_id))
        self._attempt_start_next_request()
        return req_create_id

    def measure_directly(self, req: ReqMeasureDirectly):
        """Starts the process of generating an end-to-end entangled pair to be immediately measured by sending message
        to other end node asking to start entanglement generation.

        Parameters
        ----------
        req : :class:`~qlink_interface.ReqMeasureDirectly`
            Request that needs to be handled by this method.

        """
        req_create_id = self._get_create_id()
        self._request_queue.append(QueueItem(req, req_create_id))
        self._attempt_start_next_request()
        return req_create_id

    def remote_state_preparation(self, req):
        raise NotImplementedError

    def receive(self, req: ReqReceive):
        """Allow entanglement generation with a remote EGP upon request by that EGP.

        Parameters
        ----------
        req : :object:`qlink_interface.ReqReceive`
            Request that needs to be handled by this method.

        """
        self._recv_rules[req.remote_node_id].add(req.purpose_id)

    def stop_receive(self, req: ReqStopReceive):
        """Stop allowing entanglement generation with a remote EGP upon request by that EGP.

        Parameters
        ----------
        req : :object:`qlink_interface.ReqStopReceive`
            Request that needs to be handled by this method.

        """
        self._recv_rules[req.remote_node_id].remove(req.purpose_id)

    def _is_valid_request(self, req: ReqCreateBase, origin_node_id: int):
        return req.purpose_id in self._recv_rules[origin_node_id]

    def _start_request(self, queue_item: QueueItem):
        """Begin processing a request that was put on the queue"""
        req = queue_item.qlink_create_request
        self._create_id = queue_item.create_id
        self._remote_node_id = req.remote_node_id
        self._remote_node_name = self._id_node_name_mapping[self._remote_node_id]
        self._should_keep = True
        self._active_request_create_id = self._create_id  # TODO investigate if we need a separate _active_request_create_id
        self._number_pairs_to_generate = req.number
        self._send_ask_to_other_egp(req)
        self._sequence_number = 0

        if isinstance(req, ReqMeasureDirectly):
            self._should_keep = False
            self._local_measurement_angles = {"x_1": req.x_rotation_angle_local_1,
                                              "y": req.y_rotation_angle_local,
                                              "x_2": req.x_rotation_angle_local_2}
            if tuple(self._local_measurement_angles.values()) not in self._rotation_to_measbasis:
                raise ValueError("Link layer protocol only supports measurements in X, Y and Z bases.")
        elif isinstance(req, ReqCreateAndKeep):
            self._should_keep = True
        else:
            raise NotImplementedError(f"Requests of type: {type(req)} not supported")

        return self._create_id

    @property
    def is_upstream(self):
        return self._is_upstream

    def send_repeater_activation_message(self):
        """Sends a message to all repeater nodes in the chain with a request for them to start their local SWAP-ASAP
        protocols.
        """
        reverse_chain_order = False if self.node.name in self._chain.hub_1.end_nodes.keys() else True
        repeater_node_list = copy(self._chain.repeater_nodes)
        if reverse_chain_order:
            repeater_node_list.reverse()

        max_idx = len(repeater_node_list) - 1

        for idx, repeater_node in enumerate(repeater_node_list):
            downstream_node_name = repeater_node_list[idx-1].name if idx > 0 else self.node.name
            upstream_node_name = repeater_node_list[idx+1].name if idx < max_idx else self._remote_node_name

            req = ReqSwapASAP(upstream_node_name=upstream_node_name,
                              downstream_node_name=downstream_node_name,
                              request_id=self._active_request_create_id, num=0)
            message = RemoteServiceRequest(req, SwapASAPService, origin=self.node.name, targets=[repeater_node.name])
            self.routing_service.put(message)

    def _perform_own_link_layer(self):
        """Places :class:`~nlblueprint.services.entanglement_service.ReqEntanglement` requests to the local
        entanglement generation protocol and awaits a response. If we get a failure response,
        :class:`~nlblueprint.services.entanglement_service.ResEntanglementError`, we try again until a success response,
        :class:`~nlblueprint.services.entanglement_service.ResEntanglementSuccess`, occurs.
        """
        mem_pos = self._get_free_communication_qubit_position()

        request = ReqEntanglement(remote_node_name=self._get_neighboring_repeater_node_name(), mem_pos=mem_pos)
        local_entanglement_protocol = self.node.driver[EntanglementService]
        local_entanglement_protocol.put(request=request)

        while True:
            evt_entanglement_succ = self.await_signal(sender=local_entanglement_protocol,
                                                      signal_label=ResEntanglementSuccess.__name__)
            evt_entanglement_fail = self.await_signal(sender=local_entanglement_protocol,
                                                      signal_label=ResEntanglementError.__name__)
            evt_expr = evt_entanglement_succ | evt_entanglement_fail
            yield evt_expr

            if evt_expr.first_term.value:
                self._link_identifier = self._entanglement_tracker.get_link(mem_pos)
                try:
                    if self.node.driver[QuantumMemoryManager].num_communication_qubits == 1 \
                            and self._should_keep and self.node.qmemory.num_positions > 2:
                        request = ReqMove(from_memory_position_id=mem_pos)
                        self.node.driver[QuantumMemoryManager].put(request=request)
                        yield self.await_signal(sender=self.node.driver[QuantumMemoryManager],
                                                signal_label=ResMoveSuccess.__name__)
                        response = self.node.driver[QuantumMemoryManager].get_signal_result(
                            label=ResMoveSuccess.__name__, receiver=self)
                        self._link_identifier = self._entanglement_tracker.get_link(response.memory_position_id)
                except AttributeError:
                    pass
                break
            else:
                self._free_memory()
                response = local_entanglement_protocol.get_signal_result(ResEntanglementError.__name__)
                # if entanglement was aborted, we stop trying to generate entanglement
                # if it failed for another reason, we just keep trying until success
                if response.error_code is EntanglementError.ABORTED:
                    break

    def _get_neighboring_repeater_node_name(self):
        if len(self._chain.repeater_nodes) == 0:
            return self._remote_node_name
        elif self.node.name in self._chain.hub_1.end_nodes.keys():
            return self._chain.repeater_nodes[0].name
        else:
            return self._chain.repeater_nodes[-1].name

    @property
    def is_connected(self):
        """The service is only connected if the driver at the node has one communication port and the right services.

        Requires exactly one port with either name "A" or "B" for classical communication.
        At the node's :class:`Driver`, the following services must be registered:
        - :class:`nlblueprint.services.message_handler_protocol.ClassicalRoutingService`,
        - :class:`nlblueprint.services.operation_services.MeasureService`,
        - :class:`nlblueprint.services.entanglement_service.EntanglementService`.

        """
        if ClassicalRoutingService not in self.node.driver.services:
            return False
        if MeasureService not in self.node.driver.services:
            return False
        if EntanglementService not in self.node.driver.services:
            return False
        if EntanglementTrackerService not in self.node.driver.services:
            return False
        return super().is_connected

    def _get_free_communication_qubit_position(self):
        """Get ID of a memory position corresponding to a free communication qubit.

        The free communication qubit can be used to generate entanglement.
        Currently, this method takes any qubit on the qmemory.
        Ideally, a call would be made to a memory manager to obtain a free communication qubit.
        """
        unused_positions = self.node.qmemory.unused_positions
        if len(unused_positions) > 0:
            return unused_positions[0]
        else:
            raise RuntimeError(f"Node: {self.node.name} has no free qubit available for EPR pair generation")

    @property
    def _mem_pos_most_recent_entanglement(self):
        """Get memory position where the most-recently entangled qubit is currently stored."""
        return self._entanglement_tracker.get_mem_pos(self._link_identifier)

    @property
    def _entanglement_tracker(self):
        """Entanglement tracker running on this node."""
        return self.node.driver[EntanglementTrackerService]

    def _free_memory(self):
        """Free all memory positions at this node.

        Currently, this only means setting the `in_use` flag to False.
        """
        req = ReqFreeMemory()
        self.node.driver[QuantumMemoryManager].put(request=req)

    def _clear_active_request(self):
        self._remote_node_id = None
        self._active_request = None
        self._remote_node_name = None
        self._active_request_create_id = None
        self._create_id = None
        self._number_pairs_generated = 0
        self._local_measurement_angles = None

    def _attempt_start_next_request(self):
        """Try to start executing a new item on the queue if not busy"""
        if self._active_request is not None:
            return
        if len(self._ask_queue) > 0:
            self._start_ask_request(self._ask_queue.pop(0))
            return
        if len(self._request_queue) > 0:
            self._start_request(self._request_queue.pop(0))
            return

    def _assign_header_to_message(self, message):
        """Checks if message to be sent has a header. If not, assigns it a unique one."""
        if not self._message_has_header(message):
            header = self._get_unique_header()
            message.meta["header"] = header

    @staticmethod
    def _message_has_header(message):
        """Checks if message to be sent has a header"""
        try:
            return message.meta["header"] is not None
        except KeyError:
            return False

    def _get_unique_header(self):
        """Generates unique header."""
        unique_header = self.node.name + '_' + str(self._unique_id)
        self._unique_id += 1
        return unique_header


class SwapAsapLinkLayerThatCollectsQubitsWhenMeasuring(SwapAsapEndNodeLinkLayerProtocol):
    """This version of the swap-asap link-layer protocol sends measure-directly responses with qubits, not outcomes.

    While this protocol abuses interfaces a bit by returning qubits in the place of measurement outcomes,
    using it can be convenient; by collecting qubits on measure-directly requests one can reconstruct the effective
    end-to-end state at the times of Alice's and Bob's measurements. From this, the measurement statistics can be
    obtained, which contains more information than just the result of a single measurement.
    This makes for more-efficient data collection.

    """
    def _execute_measure_directly(self):
        self._number_pairs_generated = 0
        while self._number_pairs_generated < self._number_pairs_to_generate:
            yield from self._perform_own_link_layer()
            qubit = self.node.qmemory.mem_positions[self._mem_pos_most_recent_entanglement].get_qubit(remove=True,
                                                                                                      skip_noise=False)
            self._wait_and_decide_if_measurement_outcome_should_be_kept(link_identifier=self._link_identifier,
                                                                        measurement_outcome=qubit)
            self._free_memory()
