from netsquid.protocols.nodeprotocols import NodeProtocol
from netsquid_driver.entanglement_service import ReqEntanglement, EntanglementService, \
    ResEntanglementSuccess, ResEntanglementError, ReqEntanglementAbort
from netsquid_entanglementtracker.entanglement_tracker_service import EntanglementTrackerService, ResNewLocalLink, \
    ResLocalDiscard, LinkStatus
from netsquid_driver.measurement_services import SwapService, ReqSwap, ResSwap
from netsquid.components import Message
from netsquid.components.qchannel import QuantumChannel
from netsquid_physlayer.heralded_connection import HeraldedConnection
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap_service import SwapASAPService, ResSwapASAPError, ResSwapASAPFinished, ReqSwapASAP


class SwapASAP(SwapASAPService):
    """Implementation of :class:`SwapASAPService` that works by sending requests to an
    :class:`entanglement_service.EntanglementService` and a :class:`operation_services.SwapService`.

    Uses :class:`processing_node_API.driver.Driver` to issue requests to
    :class:`entanglement_service.EntanglementService` to generate entanglement on both ports of the nodes.
    After both are successful, a request to :class:`operation_services.SwapService` is issued to perform entanglement
    swapping.
    This implementation can only handle a single :class:`ReqSwapASAP` at a time. A second will result in an error,
    unless the prespecified number of successful swaps have been performed, or a :class:`ReqSwapASAPAbort` is issued.

    Note: We make a distinction between the number of communication qubits a node has, `num_communication_qubits`,
    and the number of entanglement attempts it can perform in parallel, `n_parallel_attempts`. The first is just
    the number of qubits that can be used for communication, irrespective of if that can be done in parallel.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node`
        The node this protocol is running on.
    num_communication_qubits : int
        Number of a communication qubits the underlying node has.
    name : str, optional
        The name of this protocol.
    broadcast_responses : bool (optional)
        If True, every response sent by this service will also be broadcasted (i.e. sent as output
        on the ports

    """

    class SwapASAPSubprotocol(NodeProtocol):
        """Subprotocol to request entanglement to be generated once on a port by sending a request to the
        :class:`entanglement_service.EntanglementService`

        Meant to be used as a subprotocol of :class:`SwapASAP`.

        Parameters
        ----------
        node : :class:`~netsquid.nodes.node.Node`
            The node this protocol is running on.
        superprotocol : :class:`services.swap_asap.SwapASAP`
            Protocol that this protocol is a subprotocol of.
        port_name : str
            The name of the port that should be used to generate entanglement.
        mem_pos : int
            Memory position where entangled qubit should be stored.
        name : str
            The name of this protocol.

        """

        def __init__(self, node, superprotocol, remote_node_name: str, mem_pos, name):
            super().__init__(node=node, name=name)
            self.superprotocol = superprotocol
            self.remote_node_name = remote_node_name
            self.mem_pos = mem_pos
            self.response = None
            self.generating_entanglement = False  # used to decide if an abort request should be sent when stopping

        def run(self):

            # request entanglement
            req = ReqEntanglement(remote_node_name=self.remote_node_name, mem_pos=self.mem_pos)
            self.entanglement_service.put(req)
            self.generating_entanglement = True

            # wait for both successes and failures meant for any port/mem pos, until the right one is obtained
            succ_evt = self.await_signal(sender=self.entanglement_service,
                                         signal_label=ResEntanglementSuccess.__name__)
            error_evt = self.await_signal(sender=self.entanglement_service,
                                          signal_label=ResEntanglementError.__name__)
            while True:
                evt_expr = yield succ_evt | error_evt
                [evt] = evt_expr.triggered_events
                res = self.entanglement_service.get_signal_by_event(evt).result

                # check if response corresponds to this port and memory position
                if res.remote_node_name == self.remote_node_name and res.mem_pos == self.mem_pos:
                    if isinstance(res, ResEntanglementError):
                        self.superprotocol._handle_entanglement_error(error_code=res.error_code)
                    self.response = res  # store response to be retrieved later
                    self.generating_entanglement = False
                    break

        def abort(self):
            """When aborted while generating entanglement, an abort request is sent to the entanglement service."""
            if self.generating_entanglement:
                self.entanglement_service.put(ReqEntanglementAbort(remote_node_name=self.remote_node_name))
            self.generating_entanglement = False
            if self.node.driver[EntanglementTrackerService].get_link(mem_pos=self.mem_pos) is not None:
                self.node.driver[EntanglementTrackerService].register_local_discard_mem_pos(mem_pos=self.mem_pos)
            self.stop()

        @property
        def is_connected(self):
            """Whether protocol has been properly configured and can be started.

            Requires that all specified nodes have been set (are not None).
            Also requires a :class:`processing_node_API.driver.Driver` to be set as "driver" attribute of the node.

            Returns
            -------
            bool
                True if protocol is fully and correctly connected, otherwise False.

            """
            try:
                self.node.driver
            except AttributeError:
                return False
            return super().is_connected

        @property
        def entanglement_service(self):
            """Protocol that implements :class:`entanglement_service.EntanglementService`"""
            return self.node.driver[EntanglementService]

    DIRECTIONS = ["upstream", "downstream"]
    _DEFAULT_MEM_POS_WHEN_ALL_HAVE_BEEN_ASSIGNED_TO_SUBPROTOCOL = 0

    def __init__(self, node, num_communication_qubits=None, name=None, broadcast_responses=False):
        super().__init__(node=node, name=name)
        self.reset_attributes()
        self.num_communication_qubits = num_communication_qubits
        self.mem_pos = {self.DIRECTIONS[i]: i for i in range(2)}  # which mem pos is upstream does not matter
        self._memory_positions_by_subprotocol_names = dict()
        self.broadcast_responses = broadcast_responses
        self._unique_id = 0
        self.request_id = None
        self.num = None
        self.cutoff_time = None
        self.direction_to_node_name = {direction: None for direction in self.DIRECTIONS}

        self.entanglement_bell_indices = {direction: [] for direction in self.DIRECTIONS}
        self.swap_bell_indices = []
        self.goodness = []

    def reset_attributes(self):
        """(Re)set attributes of this protocol."""

        # reset attributes that are set by incoming swap-asap requests
        self.request_id = None
        self.num = None
        self.cutoff_time = None
        self.direction_to_node_name = {direction: None for direction in self.DIRECTIONS}

        # reset attributes that are set while fulfilling swap-asap requests
        self.entanglement_bell_indices = {direction: [] for direction in self.DIRECTIONS}
        self.swap_bell_indices = []
        self.goodness = []

    def start(self):
        """Start the fulfilment of a single :class:`ResSwapASAP`.

        Parameters
        ----------
        request_id : int
            ID of the issued :class:`ResSwapASAP`.
        num : int
            Number of times entanglement should be swapped successfully.
        cutoff_time : float
            Maximum time (ns) to store entanglement before discarding it. If 0, no cutoff time is used.
            Currently the only implemented value is 0.

        Raises
        ------
        NotImplementedError
            When a nonzero value for the cutoff time is used.

        """
        # set subprotocols, one for each of two ports meant for entanglement generation

        for remote_node_name in self.direction_to_node_name.values():
            # TODO all protocols get started, but this protocol only starts when initialized once it receives a request
            if remote_node_name is None:
                return

        for remote_node_name in self.direction_to_node_name.values():
            subprot_name = self._get_subprot_name_by_remote_node_name(remote_node_name)
            if subprot_name not in self.subprotocols:
                mem_pos = self._get_memory_position_by_subprotocol_name(subprot_name)
                self.add_subprotocol(self.SwapASAPSubprotocol(node=self.node,
                                                              superprotocol=self,
                                                              remote_node_name=remote_node_name,
                                                              mem_pos=mem_pos,
                                                              name=subprot_name),
                                     name=subprot_name)
        super().start()

    def run(self):
        """Issue entanglement-generation requests and swap requests until enough successful swaps are finished."""
        if self.request_id is None or self.num is None or self.cutoff_time is None:
            return

        while len(self.swap_bell_indices) < self.num or self.num == 0:  # length increases by 1 at each successful swap
            for remote_node_name in self.direction_to_node_name.values():
                self._start_entanglement_generation(remote_node_name)

            while True:
                # Wait for either a new link to be generated or one to be discarded.
                evt_new_link = self.await_signal(sender=self.node.driver[EntanglementTrackerService],
                                                 signal_label=ResNewLocalLink.__name__)
                evt_discard = self.await_signal(sender=self.node.driver[EntanglementTrackerService],
                                                signal_label=ResLocalDiscard.__name__)
                evt_expr = evt_new_link | evt_discard
                yield evt_expr
                # If a new link was generated, it might be the case we can swap now.
                if evt_expr.first_term.value:
                    if self._ready_to_swap:
                        yield from self._perform_swap()
                        self._log_results()
                        if self.num == 0:
                            self._send_most_recent_result()
                        self._set_memory_positions_unused()
                        break
                # If a link was discarded, we should start regenerating it as soon as possible.
                else:
                    discard_response = \
                        self.node.driver[EntanglementTrackerService].get_signal_result(ResLocalDiscard.__name__)
                    discarded_memory_position = discard_response.memory_position
                    assert discarded_memory_position is not None
                    self.node.qmemory.mem_positions[discarded_memory_position].in_use = False
                    for direction in self.DIRECTIONS:
                        if self._ready_to_start_entanglement_generation(direction):
                            self._start_entanglement_generation(direction)

        # finish if enough results are obtained
        self.finish()

    def _ready_to_start_entanglement_generation(self, direction):
        """Ready to generate entanglement along a port if it is not already being generated, or the already stored."""
        entanglement_being_generated = self._get_subprot_by_remote_node_name(self.direction_to_node_name[direction]).generating_entanglement
        entanglement_ready = self.node.driver[EntanglementTrackerService].get_link(self.mem_pos[direction]) is not None
        return not entanglement_being_generated and not entanglement_ready

    def _start_entanglement_generation(self, remote_node_name):
        self._get_subprot_by_remote_node_name(remote_node_name).start()

    @property
    def _ready_to_swap(self):
        """Whether a swap can be performed. This is the case if two entangled qubits are held in memory."""
        ent_tracker = self.node.driver[EntanglementTrackerService]
        if ent_tracker.num_available_links == 2:
            for direction in self.DIRECTIONS:
                assert ent_tracker.get_link(mem_pos=self.mem_pos[direction]) is not None
            return True
        return False

    @property
    def _entanglement_responses(self):
        """Get responses from entanglement services."""
        return {direction: self._get_subprot_by_remote_node_name(remote_node_name).response
                for direction, remote_node_name in self.direction_to_node_name.items()}

    def _handle_entanglement_error(self, error_code):
        """Check if the entanglement service has returned an error."""
        self.send_response(ResSwapASAPError(request_id=self.request_id,
                                            error_code=error_code))
        raise RuntimeError(f"Exited with error code {error_code}.")

    def _perform_swap(self):
        """Perform entanglement swap.

        Returns
        -------
        :class:`netsquid.qubits.ketstates.BellIndex` or None
            Outcome of the entanglement swap. None if the swap failed.

        """

        # request entanglement swap
        self.node.driver[SwapService].put(ReqSwap(mem_pos_1=self.mem_pos[self.DIRECTIONS[0]],
                                                  mem_pos_2=self.mem_pos[self.DIRECTIONS[1]]))

        # wait for swap to finish
        yield self.await_signal(sender=self.node.driver[SwapService],
                                signal_label=ResSwap.__name__)

    def _log_results(self):
        """Log results of entanglement swap. Does nothing if the swap was unsuccessful."""
        # obtain swap result
        swap_response = self.node.driver[SwapService].get_signal_result(ResSwap.__name__)

        # if successful, log results, else ignore them
        if swap_response is not None:  # None indicates failure
            for direction in self.DIRECTIONS:
                self.entanglement_bell_indices[direction].append(self._entanglement_responses[direction].bell_index)
            self.swap_bell_indices.append(swap_response.outcome)
            self.goodness.append(0)  # TODO give meaningful goodness parameter

    def _send_most_recent_result(self):
        """Send the most recent result that has been logged using `_log_results` as a result."""

        # prepare response
        response = ResSwapASAPFinished(request_id=self.request_id,
                                       swap_bell_indices=[self.swap_bell_indices[-1]],
                                       downstream_bell_indices=[self.entanglement_bell_indices["downstream"][-1]],
                                       upstream_bell_indices=[self.entanglement_bell_indices["upstream"][-1]],
                                       goodness=[0])

        # send response both using a signal and a message
        self.send_response(response)

    def _set_memory_positions_unused(self):
        """Set the memory positions used in entanglement generation to status "unused"."""
        self.node.qmemory.mem_positions[self.mem_pos[self.DIRECTIONS[0]]].in_use = False
        self.node.qmemory.mem_positions[self.mem_pos[self.DIRECTIONS[1]]].in_use = False

    def _get_subprot_name_by_remote_node_name(self, remote_node_name):
        """Name of `SwapASAPSubProtocol running on specific port."""
        return f"swap_asap_subprotocol_of_{self.node.name}_{remote_node_name}"

    def _get_subprot_by_remote_node_name(self, remote_node_name):
        """`SwapASAPSubProtocol running on specific port."""
        return self.subprotocols.get(self._get_subprot_name_by_remote_node_name(remote_node_name), None)

    def _get_memory_position_by_subprotocol_name(self, subprotocol_name):
        """
        Get a memory position for a subprotocol. If the subprotocol has not been assigned a memory position yet,
        this method will:

        - if possible, return a fresh memory position, not assigned to any other subprotocol
        - return an arbitrary memory position otherwise in case all memory positions have already been assigned

        Note: the number of available memory positions is the number of communication qubits the node has
        (attribute `num_communication_qubits`).

        Parameters
        ----------
        subprotocol_name : str

        Returns
        -------
        int
            Memory position
        """
        does_subprotocol_already_have_memory_position_assigned = \
            (subprotocol_name in self._memory_positions_by_subprotocol_names)
        if does_subprotocol_already_have_memory_position_assigned:
            assigned_memory_position = self._memory_positions_by_subprotocol_names[subprotocol_name]
            return assigned_memory_position
        else:
            return self._obtain_memory_position_for_new_subprotocol(subprotocol_name)

    def _obtain_memory_position_for_new_subprotocol(self, subprotocol_name):
        if self._has_more_communication_qubits_than_currently_taken():
            # unused memory positions are still available
            mem_pos = self._get_next_free_memory_position()
        else:
            mem_pos = self._DEFAULT_MEM_POS_WHEN_ALL_HAVE_BEEN_ASSIGNED_TO_SUBPROTOCOL

        # store the chosen memory position and return it
        self._memory_positions_by_subprotocol_names[subprotocol_name] = mem_pos
        return mem_pos

    def _has_more_communication_qubits_than_currently_taken(self):
        number_of_assigned_memory_positions = len(self._memory_positions_by_subprotocol_names.values())
        number_of_taken_communication_qubits = number_of_assigned_memory_positions
        total_number_of_communication_qubits = self._get_number_of_communication_qubits()
        return number_of_taken_communication_qubits < total_number_of_communication_qubits

    def _get_number_of_communication_qubits(self):
        ret = self.num_communication_qubits
        if ret is None:
            return self.node.qmemory.num_positions
        else:
            return ret

    def _get_next_free_memory_position(self):
        if len(self._memory_positions_by_subprotocol_names.values()) == 0:
            return 0
        else:
            taken_mem_pos_with_highest_index = max(self._memory_positions_by_subprotocol_names.values())
            return taken_mem_pos_with_highest_index + 1

    def finish(self):
        """Finish the protocol because either enough swaps have been performed, or it is aborted."""

        # prepare response
        downstream_bell_indices = self.entanglement_bell_indices["downstream"]
        upstream_bell_indices = self.entanglement_bell_indices["upstream"]
        response = ResSwapASAPFinished(request_id=self.request_id,
                                       swap_bell_indices=self.swap_bell_indices,
                                       downstream_bell_indices=downstream_bell_indices,
                                       upstream_bell_indices=upstream_bell_indices,
                                       goodness=self.goodness)

        # send response both using a signal and a message
        self.send_response(response)

        self.reset_attributes()

    def send_response(self, response, name=None):
        """Send a response via a signal and, additionally, via a message, and check if it has the proper format.

        Response is first type-checked, then sent as a signal by the protocol.
        If the protocol was initialized with `broadcast_responses=True`, the signal is then also sent as a message
        on every port of the node.

        Parameters
        ----------
        response : :class:`collections.namedtuple` or object
            The response instance.
        name : str or None, optional
            The identifier used for this response.
            Default :meth:`~netsquid.protocols.serviceprotocol.ServiceProtocol.get_name` of the request.

        Raises
        ------
        ServiceError
            If the name doesn't match to the request type.

        Note
        ----
        If the response is a :obj:`ResSwapASAPFinished` and the lists of Bell indices for the upstream link, downstream
        link and entanglement swap don't have the same length,
        an error response :obj:`ResSwapASAPError` is sent instead.
        This is because every cycle of the swap-ASAP protocol should yield one Bell index for the downstream link,
        one for the upstream link, and one for the entanglement swap. Thus, if one of the lists is longer than another,
        something must have gone wrong.

        """
        super().send_response(response=response, name=name)
        if self.broadcast_responses:
            # TODO remove or figure out if needed and connect to routingservice broadcast
            for port_name in self.COMM_PORT_NAMES:
                message = Message(items=response, sender_id=self.node.ID, type="repeater_response",
                                  forward=FORWARD_CHAIN)
                self._assign_header_to_message(message)
                port = self.node.ports[port_name]
                port.tx_output(message)

    def swap_asap(self, req: ReqSwapASAP):
        """Start generating entanglement with both neighbours, and perform entanglement swap when successful.

        This is repeated until either the predefined number of successful swaps has been achieved, or the operation
        is aborted by :meth:`~SwapASAPService.abort`.

        Parameters
        ----------
        req : :obj:`ReqSwapASAP`
            Request that needs to be handled by this method.
            Needs to have additional "port_name" attribute to identify through which port the request arrived
            in a message.

        Raises
        ------
        RunTimeError
            If the protocol is already running.

        """
        super().swap_asap(req)
        if self.node.driver[EntanglementTrackerService].num_available_links != 0:
            raise RuntimeError("SwapASAP cannot start when there already is active entanglement at the node.")
        if self.is_running:  # can only deal with one request at a time TODO: should there be a queue?
            self.send_response(ResSwapASAPError(request_id=req.request_id,
                                                error_code=0))
            raise RuntimeError("SwapASAP received ReqSwapASAP while it was already running.")

        self.direction_to_node_name["upstream"] = req.upstream_node_name
        self.direction_to_node_name["downstream"] = req.downstream_node_name
        self.request_id = req.request_id
        self.num = req.num
        if req.cutoff_time != 0:  # TODO: implement cutoff time
            raise NotImplementedError("Cutoff time currently not implemented, set cutoff_time = 0.")
        self.cutoff_time = req.cutoff_time

        # start fulfilling request
        self.start()

    def abort(self, req):
        """Abort ongoing swap-ASAP operation.

        Parameters
        ----------
        req : :obj:`ReqSwapASAPAbort`
            Request that needs to be handled by this method.

        """
        super().abort(req)
        if req.request_id == self.request_id:
            self.stop()  # stop ongoing operations
            for prot in self.subprotocols.values():  # abort subprotocols
                prot.abort()
            self._set_memory_positions_unused()
            self.reset_attributes()
            for link_identifier in \
                    self.node.driver[EntanglementTrackerService].get_links_by_status(LinkStatus.AVAILABLE):
                self.node.driver[EntanglementTrackerService].register_discard(link_identifier=link_identifier)
        else:
            raise RuntimeError("Trying to abort a request that is not currently being handled")

    @property
    def is_connected(self):
        """Whether protocol has been properly configured and can be started.

        Requires that all specified nodes have been set (are not None).
        Each node needs to have ports with names as defined by :prop:`SwapASAP.COMM_PORT_NAMES` and
        :prop:`SwapASAP.ENT_PORT_NAMES`.
        Also requires a :class:`processing_node_API.driver.Driver` to be set as "driver" attribute of the node,
        and requires both an :class:`entanglement_service.EntanglementService` and
        :class:`operation_services.SwapService` to be registered at the driver.

        Returns
        -------
        bool
            True if protocol is fully and correctly connected, otherwise False.

        """
        try:
            driver = self.node.driver
            assert isinstance(driver[EntanglementService], EntanglementService)
            assert isinstance(driver[SwapService], SwapService)
        except (AttributeError, KeyError):
            return False
        return super().is_connected

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


class SwapASAPOneSequentialRepeater(SwapASAP):
    """Implementation of :class:`SwapASAPService` that works by sending requests to an
    :class:`entanglement_service.EntanglementService` and a :class:`operation_services.SwapService`, assuming
    setup of one sequential repeater.

    The functionality is identical to the parent class, with slight changes to the logic. While in the parent class
    requests are issued simultaneously to :class:`entanglement_service.EntanglementService` to generate entanglement on
    both ports of the nodes, here a request is issued first to whichever neighbouring node is physically further away,
    as determined by :method:`_get_port_name_of_longest_side`. Furthermore, whenever a discard of generated entanglement
    happens due to a cut-off timer going off, entanglement generation on the shortest side is aborted and begins on the
    longest side again.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node`
        The node this protocol is running on.
    num_communication_qubits : int
        Number of a communication qubits the underlying node has.
    name : str, optional
        The name of this protocol.
    broadcast_responses : bool (optional)
        If True, every response sent by this service will also be broadcasted (i.e. sent as output
        on the ports

    """
    # TODO this class is not fixed yet, for it to work the constructor needs to be given the distances to neighboring nodes
    def __init__(self, node, num_communication_qubits=None, name=None, broadcast_responses=False):
        self._port_of_longest_side = None
        self._port_of_shortest_side = None
        self._unique_id = 0
        super().__init__(node=node, name=name, num_communication_qubits=num_communication_qubits,
                         broadcast_responses=broadcast_responses)

    def _get_port_name_of_longest_side(self):
        """Get name of port being used to generate entanglement with the neighbouring node that is most distant."""

        connection_lengths = {}
        for port in self.ENT_PORT_NAMES:
            connection = self.node.ports[port].connected_port.component
            assert isinstance(connection, HeraldedConnection)
            qchannels = [ch for ch in connection.subcomponents.values() if isinstance(ch, QuantumChannel)]
            connection_lengths[port] = sum(qchannel.properties["length"] for qchannel in qchannels)

        return max(connection_lengths, key=lambda k: connection_lengths[k])

    def run(self):
        """Issue entanglement-generation requests and swap requests until enough successful swaps are finished."""

        if self.request_id is None or self.num is None or self.cutoff_time is None:
            return
        if self.node.driver[EntanglementService].num_parallel_attempts != 1:
            raise RuntimeError(
                "SwapASAPOneSequentialRepeater should be run on nodes capable of generating 1 link in parallel, not {}."
                .format(self.node.driver[EntanglementService].num_parallel_attempts))

        self._port_of_longest_side = self._get_port_name_of_longest_side()
        self._port_of_shortest_side = \
            [port_name for port_name in self.ENT_PORT_NAMES if port_name != self._port_of_longest_side][0]

        while len(self.swap_bell_indices) < self.num or self.num == 0:  # length increases by 1 at each successful swap

            self._start_entanglement_generation(self._port_of_longest_side)
            while True:
                # Wait for either a new link to be generated or one to be discarded.
                evt_new_link = self.await_signal(sender=self.node.driver[EntanglementTrackerService],
                                                 signal_label=ResNewLocalLink.__name__)
                evt_discard = self.await_signal(sender=self.node.driver[EntanglementTrackerService],
                                                signal_label=ResLocalDiscard.__name__)
                evt_expr = evt_new_link | evt_discard
                yield evt_expr
                # If a new link was generated, we can either swap or we are ready to start on the shorter side.
                if evt_expr.first_term.value:
                    if self._ready_to_swap:
                        yield from self._perform_swap()
                        self._log_results()
                        if self.num == 0:
                            self._send_most_recent_result()
                        self._set_memory_positions_unused()
                        break
                    else:
                        assert self._ready_to_start_entanglement_generation(self._port_of_shortest_side)
                        self._start_entanglement_generation(self._port_of_shortest_side)
                # If a link was discarded, we should abort entanglement generation on shortest side, ensure that the
                # corresponding end node also aborts by sending it a request and start regenerating on the longest side
                # as soon as possible.
                else:
                    discard_response = \
                        self.node.driver[EntanglementTrackerService].get_signal_result(ResLocalDiscard.__name__)
                    # we expect the memory position being discarded to always be the one corresponding to the long side
                    assert discard_response.memory_position == self.mem_pos[self._port_of_longest_side]

                    # abort entanglement generation on shortest side
                    self._get_subprot_by_port_name(self._port_of_shortest_side).abort()
                    self._set_memory_positions_unused()

                    # The request for aborting entanglement generation will be sent to the end node on the shortest
                    # side, whose entanglement generation port has the same name as the port of the repeater node
                    # (this one) used for entanglement generation on the longest side
                    request = ReqEntanglementAbort(port_name=self._port_of_longest_side)
                    message = Message([request], **{"type": TYPE_REQUEST, "service": EntanglementService})
                    self._assign_header_to_message(message)
                    [port_name_classical_short_side] = self._port_of_shortest_side.split("ENT_")[1]
                    self.node.ports[port_name_classical_short_side].tx_output(message)

                    # try again by beginning entanglement generation on longest side
                    assert self._ready_to_start_entanglement_generation(self._port_of_longest_side)
                    self._start_entanglement_generation(self._port_of_longest_side)

        # finish if enough results are obtained
        self.finish()
