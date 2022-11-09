import logging
from typing import Generator, List, Optional

import netsquid as ns
from netqasm.sdk.build_epr import (
    SER_CREATE_IDX_NUMBER,
    SER_CREATE_IDX_TYPE,
    SER_RESPONSE_KEEP_IDX_BELL_STATE,
    SER_RESPONSE_KEEP_IDX_GOODNESS,
    SER_RESPONSE_KEEP_LEN,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS,
    SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME,
    SER_RESPONSE_MEASURE_LEN,
)
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z
from netsquid.qubits.ketstates import BellIndex
from qlink_interface import (
    ReqCreateAndKeep,
    ReqCreateBase,
    ReqMeasureDirectly,
    ReqReceive,
    ReqRemoteStatePrep,
    ResCreateAndKeep,
    ResMeasureDirectly,
)

from pydynaa import EventExpression
from squidasm.qoala.sim.constants import PI
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memmgr import AllocError, MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory
from squidasm.qoala.sim.message import Message
from squidasm.qoala.sim.netstackinterface import NetstackInterface
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.qdevice import QDevice, QDeviceCommand
from squidasm.qoala.sim.requests import (
    EprCreateType,
    NetstackBreakpointCreateRequest,
    NetstackBreakpointReceiveRequest,
    NetstackCreateRequest,
    NetstackReceiveRequest,
    T_NetstackReqeust,
)


class NetstackProcessor:
    def __init__(self, interface: NetstackInterface) -> None:
        self._interface = interface

        self._name = f"{interface.name}_NetstackProcessor"

        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )

        # memory of current program, only not-None when processor is active
        self._current_prog_mem: Optional[ProgramMemory] = None

    def _prog_mem(self) -> ProgramMemory:
        # May only be called when processor is active
        assert self._current_prog_mem is not None
        return self._current_prog_mem

    @property
    def qdevice(self) -> QDevice:
        return self._interface.qdevice

    def remote_id_to_peer_name(self, remote_id: int) -> str:
        node_info = self._local_env.get_global_env().get_nodes()[remote_id]
        # TODO figure out why mypy does not like this
        return node_info.name  # type: ignore

    def get_shared_mem(self, pid: int) -> SharedMemory:
        prog_mem = self._processes[pid].prog_memory
        return prog_mem.shared_mem

    def _read_request_args_array(self, pid: int, array_addr: int) -> List[int]:
        shared_mem = self.get_shared_mem(pid)
        # TODO figure out why mypy does not like this
        return shared_mem.get_array(array_addr)  # type: ignore

    def _create_link_layer_create_request(
        # self, remote_id: int, args: List[int], epr_socket: EprSocket
        self,
        request: NetstackCreateRequest,
    ) -> ReqCreateBase:
        """Construct a link layer request from application request info.

        :param remote_id: ID of remote node
        :param args: NetQASM array elements from the arguments array specified by the
            application
        :return: link layer request object
        """

        if request.typ == EprCreateType.CREATE_KEEP:
            ll_request = ReqCreateAndKeep(
                remote_node_id=request.remote_id,
                number=request.num_pairs,
                minimum_fidelity=request.fidelity,
            )
        elif request.typ == EprCreateType.MEASURE_DIRECTLY:
            ll_request = ReqMeasureDirectly(
                remote_node_id=request.remote_id,
                number=request.num_pairs,
                minimum_fidelity=request.fidelity,
            )
        elif request.typ == EprCreateType.REMOTE_STATE_PREP:
            ll_request = ReqRemoteStatePrep(
                remote_node_id=request.remote_id,
                number=request.num_pairs,
                minimum_fidelity=request.fidelity,
            )
        else:
            raise ValueError(f"Unsupported create type {request.typ}")
        return ll_request

    def assign(
        self, process: IqoalaProcess, request: T_NetstackReqeust
    ) -> Generator[EventExpression, None, int]:

        if isinstance(request, NetstackCreateRequest):
            yield from self.handle_create_request(request)
            self._logger.debug("create request done")
        elif isinstance(request, NetstackReceiveRequest):
            yield from self.handle_receive_request(request)
            self._logger.debug("receive request done")
        elif isinstance(request, NetstackBreakpointCreateRequest):
            yield from self.handle_breakpoint_create_request(request)
            self._logger.debug("breakpoint create request done")
        elif isinstance(request, NetstackBreakpointReceiveRequest):
            yield from self.handle_breakpoint_receive_request(request)
            self._logger.debug("breakpoint receive request done")

    def handle_create_request(
        self, req: NetstackCreateRequest
    ) -> Generator[EventExpression, None, None]:
        """Issue a request to create entanglement with a remote node.

        :param req: request info
        """

        # Check that the corresponding EPR socket exists.
        epr_socket = self._interface.egpmgr.get_egp(req.remote_node_id)

        # Read request parameters from the corresponding NetQASM array.
        args = self._read_request_args_array(req.pid, req.arg_array_addr)

        # Create the link layer request object.
        request = self._create_link_layer_request(req.remote_node_id, args, epr_socket)

        # Send it to the receiver node and wait for an acknowledgement.
        peer = self.remote_id_to_peer_name(req.remote_node_id)
        self._interface.send_peer_msg(peer, Message(content=request))
        peer_msg = yield from self._interface.receive_peer_msg(peer)
        self._logger.debug(f"received peer msg: {peer_msg}")

        # Handle the request.
        if isinstance(request, ReqCreateAndKeep):
            yield from self.handle_create_ck_request(req, request)
        elif isinstance(request, ReqMeasureDirectly):
            yield from self.handle_create_md_request(req, request)

    def handle_create_ck_request(
        self, process: IqoalaProcess, req: NetstackCreateRequest
    ) -> Generator[EventExpression, None, None]:
        """Handle a Create and Keep request as the initiator/creator, until all
        pairs have been created.

        This method uses the EGP protocol to create and measure EPR pairs with
        the remote node. It will fully complete the request before returning. If
        the pair created by the EGP protocol is another Bell state than Phi+,
        local gates are applied to do a correction, such that the final
        delivered pair is always Phi+.

        The method can however yield (i.e. give control back to the simulator
        scheduler) in the following cases: - no communication qubit is
        available; this method will resume when a
          SIGNAL_MEMORY_FREED is given (currently only the processor can do
          this)
        - when waiting for the EGP protocol to produce the next pair; this
          method resumes when the pair is delivered
        - a Bell correction gate is applied

        This method does not return anything. This method has the side effect
        that NetQASM array value are written to.

        :param req: application request info (app ID and NetQASM array IDs)
        :param request: link layer request object
        """
        num_pairs = req.num_pairs
        ll_request = self._create_link_layer_create_request(req)

        shared_mem = process.prog_memory.shared_mem

        self._logger.info(f"putting CK request to EGP for {num_pairs} pairs")
        self._logger.info(f"qubit IDs specified by application: {req.virt_qubit_ids}")
        self._logger.info(f"splitting request into {num_pairs} 1-pair requests")
        ll_request.number = 1

        start_time = ns.sim_time()

        for pair_index in range(num_pairs):
            self._logger.info(f"trying to allocate comm qubit for pair {pair_index}")
            virt_id = req.virt_qubit_ids[pair_index]
            while True:
                try:
                    self._interface.memmgr.allocate(process.pid, virt_id)
                    break
                except AllocError:
                    self._logger.info("no comm qubit available, waiting...")

                    # Wait for a signal indicating the communication qubit might be free
                    # again.
                    yield from self._interface.await_memory_freed_signal()
                    self._logger.info(
                        "a 'free' happened, trying again to allocate comm qubit..."
                    )

            # Put the request to the EGP.
            self._logger.info(f"putting CK request for pair {pair_index}")
            self._interface.put_request(req.remote_id, ll_request)

            # Wait for a signal from the EGP.
            self._logger.info(f"waiting for result for pair {pair_index}")
            result = yield from self._interface.await_result_create_keep(req.remote_id)
            self._logger.info(f"got result for pair {pair_index}: {result}")

            # Bell state corrections. Resulting state is always Phi+ (i.e. B00).
            if result.bell_state == BellIndex.B00:
                pass
            elif result.bell_state == BellIndex.B01:
                commands = [QDeviceCommand(INSTR_ROT_X, [0], angle=PI)]
                yield self._interface.qdevice.execute_commands(commands)
            elif result.bell_state == BellIndex.B10:
                commands = [QDeviceCommand(INSTR_ROT_Z, [0], angle=PI)]
                yield self._interface.qdevice.execute_commands(commands)
            elif result.bell_state == BellIndex.B11:
                commands = [
                    QDeviceCommand(INSTR_ROT_X, [0], angle=PI),
                    QDeviceCommand(INSTR_ROT_Z, [0], angle=PI),
                ]
                yield self._interface.qdevice.execute_commands(commands)

            gen_duration_ns_float = ns.sim_time() - start_time
            gen_duration_us_int = int(gen_duration_ns_float / 1000)
            self._logger.info(f"gen duration (us): {gen_duration_us_int}")

            # Length of response array slice for a single pair.
            slice_len = SER_RESPONSE_KEEP_LEN

            # Populate results array.
            for i in range(slice_len):
                # Write -1 to unused array elements.
                value = -1

                # Write corresponding result value to the other array elements.
                if i == SER_RESPONSE_KEEP_IDX_GOODNESS:
                    value = gen_duration_us_int
                if i == SER_RESPONSE_KEEP_IDX_BELL_STATE:
                    value = result.bell_state

                # Calculate array element location.
                arr_index = slice_len * pair_index + i

                shared_mem.set_array_value(req.result_array_addr, arr_index, value)
            self._logger.debug(
                f"wrote to @{req.result_array_addr}[{slice_len * pair_index}:"
                f"{slice_len * pair_index + slice_len}] for app ID {process.pid}"
            )
            self._interface.send_qnos_msg(Message(content="wrote to array"))

    def handle_create_md_request(
        self, req: NetstackCreateRequest, request: ReqMeasureDirectly
    ) -> Generator[EventExpression, None, None]:
        """Handle a Create and Measure request as the initiator/creator, until all
        pairs have been created and measured.

        This method uses the EGP protocol to create EPR pairs with the remote node.
        It will fully complete the request before returning.

        No Bell state corrections are done. This means that application code should
        use the result information to check, for each pair, the generated Bell state
        and possibly post-process the measurement outcomes.

        The method can yield (i.e. give control back to the simulator scheduler) in
        the following cases:
        - no communication qubit is available; this method will resume when a
          SIGNAL_MEMORY_FREED is given (currently only the processor can do this)
        - when waiting for the EGP protocol to produce the next pair; this method
          resumes when the pair is delivered

        This method does not return anything.
        This method has the side effect that NetQASM array value are written to.

        :param req: application request info (app ID and NetQASM array IDs)
        :param request: link layer request object
        """

        # Put the reqeust to the EGP.
        self._interface.put_request(req.remote_node_id, request)

        results: List[ResMeasureDirectly] = []

        # Wait for all pairs to be created. For each pair, the EGP sends a separate
        # signal that is awaited here. Only after the last pair, we write the results
        # to the array. This is done since the whole request (i.e. all pairs) is
        # expected to finish in a short time anyway. However, writing results for a
        # pair as soon as they are done may be implemented in the future.
        for _ in range(request.number):
            self._interface.memmgr.allocate(req.pid, 0)

            result = yield from self._interface.await_result_measure_directly(
                req.remote_node_id
            )
            self._logger.debug(f"bell index: {result.bell_state}")
            results.append(result)
            self._interface.memmgr.free(req.pid, 0)

        shared_mem = self.get_shared_mem(req.pid)

        # Length of response array slice for a single pair.
        slice_len = SER_RESPONSE_MEASURE_LEN

        # Populate results array.
        for pair_index in range(request.number):
            result = results[pair_index]

            for i in range(slice_len):
                # Write -1 to unused array elements.
                value = -1

                # Write corresponding result value to the other array elements.
                if i == SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME:
                    value = result.measurement_outcome
                elif i == SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS:
                    value = result.measurement_basis.value
                elif i == SER_RESPONSE_KEEP_IDX_BELL_STATE:
                    value = result.bell_state.value

                # Calculate array element location.
                arr_index = slice_len * pair_index + i

                shared_mem.set_array_value(req.result_array_addr, arr_index, value)

        self._interface.send_qnos_msg(Message(content="wrote to array"))

    def handle_receive_ck_request(
        self, req: NetstackReceiveRequest, request: ReqCreateAndKeep
    ) -> Generator[EventExpression, None, None]:
        """Handle a Create and Keep request as the receiver, until all pairs have
        been created.

        This method uses the EGP protocol to create EPR pairs with the remote
        node. It will fully complete the request before returning.

        If the pair created by the EGP protocol is another Bell state than Phi+,
        it is assumed that the *other* node applies local gates such that the
        final delivered pair is always Phi+.

        The method can yield (i.e. give control back to the simulator scheduler)
        in the following cases: - no communication qubit is available; this
        method will resume when a
          SIGNAL_MEMORY_FREED is given (currently only the processor can do
          this)
        - when waiting for the EGP protocol to produce the next pair; this
          method resumes when the pair is delivered

        This method does not return anything. This method has the side effect
        that NetQASM array value are written to.

        :param req: application request info (app ID and NetQASM array IDs)
        :param request: link layer request object
        """
        assert isinstance(request, ReqCreateAndKeep)

        num_pairs = request.number

        shared_mem = self.get_shared_mem(req.pid)

        self._logger.info(f"putting CK request to EGP for {num_pairs} pairs")
        self._logger.info(f"splitting request into {num_pairs} 1-pair requests")

        start_time = ns.sim_time()

        for pair_index in range(num_pairs):
            self._logger.info(f"trying to allocate comm qubit for pair {pair_index}")
            virt_id = shared_mem.get_array_value(req.qubit_array_addr, pair_index)
            while True:
                try:
                    self._interface.memmgr.allocate(req.pid, virt_id)
                    break
                except AllocError:
                    self._logger.info("no comm qubit available, waiting...")

                    # Wait for a signal indicating the communication qubit might be free
                    # again.
                    yield from self._interface.await_memory_freed_signal()
                    self._logger.info(
                        "a 'free' happened, trying again to allocate comm qubit..."
                    )

            # Put the request to the EGP.
            self._logger.info(f"putting CK request for pair {pair_index}")
            self._interface.put_request(
                req.remote_node_id, ReqReceive(req.remote_node_id)
            )
            self._logger.info(f"waiting for result for pair {pair_index}")

            # Wait for a signal from the EGP.
            result = yield from self._interface.await_result_create_keep(
                req.remote_node_id
            )
            self._logger.info(f"got result for pair {pair_index}: {result}")

            gen_duration_ns_float = ns.sim_time() - start_time
            gen_duration_us_int = int(gen_duration_ns_float / 1000)
            self._logger.info(f"gen duration (us): {gen_duration_us_int}")

            # Length of response array slice for a single pair.
            slice_len = SER_RESPONSE_KEEP_LEN

            for i in range(slice_len):
                # Write -1 to unused array elements.
                value = -1

                # Write corresponding result value to the other array elements.
                if i == SER_RESPONSE_KEEP_IDX_GOODNESS:
                    value = gen_duration_us_int
                if i == SER_RESPONSE_KEEP_IDX_BELL_STATE:
                    value = result.bell_state.value

                # Calculate array element location.
                arr_index = slice_len * pair_index + i

                shared_mem.set_array_value(req.result_array_addr, arr_index, value)
            self._logger.debug(
                f"wrote to @{req.result_array_addr}[{slice_len * pair_index}:"
                f"{slice_len * pair_index + slice_len}] for app ID {req.pid}"
            )
            self._interface.send_qnos_msg(Message(content="wrote to array"))

    def handle_receive_md_request(
        self, req: NetstackReceiveRequest, request: ReqMeasureDirectly
    ) -> Generator[EventExpression, None, None]:
        """Handle a Create and Measure request as the receiver, until all
        pairs have been created and measured.

        This method uses the EGP protocol to create EPR pairs with the remote node.
        It will fully complete the request before returning.

        No Bell state corrections are done. This means that application code should
        use the result information to check, for each pair, the generated Bell state
        and possibly post-process the measurement outcomes.

        The method can yield (i.e. give control back to the simulator scheduler)
        in the following cases: - no communication qubit is available; this
        method will resume when a
          SIGNAL_MEMORY_FREED is given (currently only the processor can do
          this)
        - when waiting for the EGP protocol to produce the next pair; this
          method resumes when the pair is delivered

        This method does not return anything. This method has the side effect
        that NetQASM array value are written to.

        :param req: application request info (app ID and NetQASM array IDs)
        :param request: link layer request object
        """
        assert isinstance(request, ReqMeasureDirectly)

        self._interface.put_request(req.remote_node_id, ReqReceive(req.remote_node_id))

        results: List[ResMeasureDirectly] = []

        for _ in range(request.number):
            self._interface.memmgr.allocate(req.pid, 0)

            result = yield from self._interface.await_result_measure_directly(
                req.remote_node_id
            )
            results.append(result)

            self._interface.memmgr.free(req.pid, 0)

        shared_mem = self.get_shared_mem(req.pid)

        # Length of response array slice for a single pair.
        slice_len = SER_RESPONSE_MEASURE_LEN

        # Populate results array.
        for pair_index in range(request.number):
            result = results[pair_index]

            for i in range(slice_len):
                # Write -1 to unused array elements.
                value = -1

                # Write corresponding result value to the other array elements.
                if i == SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME:
                    value = result.measurement_outcome
                elif i == SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS:
                    value = result.measurement_basis.value
                elif i == SER_RESPONSE_KEEP_IDX_BELL_STATE:
                    value = result.bell_state.value

                # Calculate array element location.
                arr_index = slice_len * pair_index + i

                shared_mem.set_array_value(req.result_array_addr, arr_index, value)

            self._interface.send_qnos_msg(Message(content="wrote to array"))

    def handle_receive_request(
        self, req: NetstackReceiveRequest
    ) -> Generator[EventExpression, None, None]:
        """Issue a request to receive entanglement from a remote node.

        :param req: request info
        """

        # Wait for the network stack in the remote node to get the corresponding
        # 'create' request from its local application and send it to us.
        # NOTE: we do not check if the request from the other node matches our own
        # request. Also, we simply block until synchronizing with the other node,
        # and then fully handle the request. There is no support for queueing
        # and/or interleaving multiple different requests.
        peer = self.remote_id_to_peer_name(req.remote_node_id)
        msg = yield from self._interface.receive_peer_msg(peer)
        create_request = msg.content
        self._logger.debug(f"received {create_request} from peer")

        # Acknowledge to the remote node that we received the request and we will
        # start handling it.
        self._logger.debug("sending 'ready' to peer")
        self._interface.send_peer_msg(peer, Message(content="ready"))

        # Handle the request, based on the type that we now know because of the
        # other node.
        if isinstance(create_request, ReqCreateAndKeep):
            yield from self.handle_receive_ck_request(req, create_request)
        elif isinstance(create_request, ReqMeasureDirectly):
            yield from self.handle_receive_md_request(req, create_request)

    def handle_breakpoint_create_request(
        self, request: NetstackBreakpointCreateRequest
    ) -> Generator[EventExpression, None, None]:
        # Use epr sockets for this process to get all relevant remote nodes.
        epr_sockets = self._processes[request.pid].epr_sockets
        remote_ids = [esck.remote_id for esck in epr_sockets.values()]
        remote_names = [self.remote_id_to_peer_name(id) for id in remote_ids]

        # Synchronize with the remote nodes.
        for peer in remote_names:
            self._interface.send_peer_msg(peer, Message(content="breakpoint start"))

        for peer in remote_names:
            response = yield from self._interface.receive_peer_msg(peer)
            assert response.content == "breakpoint start"

        # Remote nodes are now ready. Notify the processor.
        self._interface.send_qnos_msg(Message(content="breakpoint ready"))

        # Wait for the processor to finish handling the breakpoint.
        processor_msg = yield from self._interface.receive_qnos_msg()
        assert processor_msg.content == "breakpoint end"

        # Tell the remote nodes that the breakpoint has finished.
        for peer in remote_names:
            self._interface.send_peer_msg(peer, Message(content="breakpoint end"))

        # Wait for the remote node to have finsihed as well.
        for peer in remote_names:
            response = yield from self._interface.receive_peer_msg(peer)
            assert response.content == "breakpoint end"

        # Notify the processor that we are done.
        self._interface.send_qnos_msg(Message(content="breakpoint finished"))

    def handle_breakpoint_receive_request(
        self, request: NetstackBreakpointReceiveRequest
    ) -> Generator[EventExpression, None, None]:
        # Use epr sockets for this process to get all relevant remote nodes.
        epr_sockets = self._processes[request.pid].epr_sockets
        remote_ids = [esck.remote_id for esck in epr_sockets.values()]
        remote_names = [self.remote_id_to_peer_name(id) for id in remote_ids]

        # Synchronize with the remote nodes.
        for peer in remote_names:
            msg = yield from self._interface.receive_peer_msg(peer)
            assert msg.content == "breakpoint start"

        for peer in remote_names:
            self._interface.send_peer_msg(peer, Message(content="breakpoint start"))

        # Notify the processor we are ready to handle the breakpoint.
        self._interface.send_qnos_msg(Message(content="breakpoint ready"))

        # Wait for the processor to finish handling the breakpoint.
        processor_msg = yield from self._interface.receive_qnos_msg()
        assert processor_msg.content == "breakpoint end"

        # Wait for the remote nodes to finish and tell it we are finished as well.
        for peer in remote_names:
            peer_msg = yield from self._interface.receive_peer_msg(peer)
            assert peer_msg.content == "breakpoint end"

        for peer in remote_names:
            self._interface.send_peer_msg(peer, Message(content="breakpoint end"))

        # Notify the processor that we are done.
        self._interface.send_qnos_msg(Message(content="breakpoint finished"))
