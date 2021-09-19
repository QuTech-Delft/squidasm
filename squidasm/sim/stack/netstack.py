from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Generator, List, Optional

from netsquid.components import QuantumProcessor
from netsquid.components.component import Component, Port
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z
from netsquid.components.qprogram import QuantumProgram
from netsquid.nodes import Node
from netsquid.qubits.ketstates import BellIndex
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from qlink_interface import (
    ReqCreateAndKeep,
    ReqCreateBase,
    ReqMeasureDirectly,
    ReqReceive,
    ResCreateAndKeep,
    ResMeasureDirectly,
)
from qlink_interface.interface import ReqRemoteStatePrep

from pydynaa import EventExpression
from squidasm.sim.stack.common import (
    AllocError,
    AppMemory,
    ComponentProtocol,
    NetstackBreakpointCreateRequest,
    NetstackBreakpointReceiveRequest,
    NetstackCreateRequest,
    NetstackReceiveRequest,
    PhysicalQuantumMemory,
    PortListener,
)
from squidasm.sim.stack.egp import EgpProtocol
from squidasm.sim.stack.signals import SIGNAL_PEER_NSTK_MSG, SIGNAL_PROC_NSTK_MSG

if TYPE_CHECKING:
    from squidasm.sim.stack.qnos import Qnos

PI = math.pi
PI_OVER_2 = math.pi / 2


class NetstackComponent(Component):
    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.name}_netstack")
        self._node = node
        self.add_ports(["proc_out", "proc_in"])
        self.add_ports(["peer_out", "peer_in"])

    @property
    def processor_in_port(self) -> Port:
        return self.ports["proc_in"]

    @property
    def processor_out_port(self) -> Port:
        return self.ports["proc_out"]

    @property
    def peer_in_port(self) -> Port:
        return self.ports["peer_in"]

    @property
    def peer_out_port(self) -> Port:
        return self.ports["peer_out"]

    @property
    def node(self) -> Node:
        return self._node


@dataclass
class EprSocket:
    socket_id: int
    remote_id: int


class Netstack(ComponentProtocol):
    def __init__(self, comp: NetstackComponent, qnos: Qnos) -> None:
        super().__init__(name=f"{comp.name}_protocol", comp=comp)
        self._comp = comp
        self._qnos = qnos

        self.add_listener(
            "processor",
            PortListener(self._comp.processor_in_port, SIGNAL_PROC_NSTK_MSG),
        )
        self.add_listener(
            "peer",
            PortListener(self._comp.peer_in_port, SIGNAL_PEER_NSTK_MSG),
        )

        self._egp: Optional[EgpProtocol] = None
        self._epr_sockets: Dict[int, List[EprSocket]] = {}  # app ID -> [socket]

    def assign_ll_protocol(self, prot: MagicLinkLayerProtocolWithSignaling) -> None:
        self._egp = EgpProtocol(self._comp.node, prot)

    def open_epr_socket(self, app_id: int, socket_id: int, remote_node_id: int) -> None:
        if app_id not in self._epr_sockets:
            self._epr_sockets[app_id] = []
        self._epr_sockets[app_id].append(EprSocket(socket_id, remote_node_id))

    def _send_processor_msg(self, msg: str) -> None:
        self._comp.processor_out_port.tx_output(msg)

    def _receive_processor_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("processor", SIGNAL_PROC_NSTK_MSG))

    def _send_peer_msg(self, msg: str) -> None:
        self._comp.peer_out_port.tx_output(msg)

    def _receive_peer_msg(self) -> Generator[EventExpression, None, str]:
        return (yield from self._receive_msg("peer", SIGNAL_PEER_NSTK_MSG))

    def start(self) -> None:
        super().start()
        if self._egp:
            self._egp.start()

    def stop(self) -> None:
        if self._egp:
            self._egp.stop()
        super().stop()

    def _read_request_args_array(self, app_id: int, array_addr: int) -> List[int]:
        app_mem = self.app_memories[app_id]
        app_mem.get_array(array_addr)
        return app_mem.get_array(array_addr)

    def _construct_request(self, remote_id: int, args: List[int]) -> ReqCreateBase:
        typ = args[0]
        assert typ is not None
        num_pairs = args[1]
        assert num_pairs is not None

        MINIMUM_FIDELITY = 0.99

        if typ == 0:
            request = ReqCreateAndKeep(
                remote_node_id=remote_id,
                number=num_pairs,
                minimum_fidelity=MINIMUM_FIDELITY,
            )
        elif typ == 1:
            request = ReqMeasureDirectly(
                remote_node_id=remote_id,
                number=num_pairs,
                minimum_fidelity=MINIMUM_FIDELITY,
            )
        elif typ == 2:
            request = ReqRemoteStatePrep(
                remote_node_id=remote_id,
                number=num_pairs,
                minimum_fidelity=MINIMUM_FIDELITY,
            )
        else:
            raise ValueError(f"Unsupported create type {typ}")
        return request

    @property
    def app_memories(self) -> Dict[int, AppMemory]:
        return self._qnos.app_memories

    @property
    def physical_memory(self) -> PhysicalQuantumMemory:
        return self._qnos.physical_memory

    @property
    def qdevice(self) -> QuantumProcessor:
        return self._comp.node.qdevice

    def find_epr_socket(
        self, app_id: int, sck_id: int, rem_id: int
    ) -> Optional[EprSocket]:
        if app_id not in self._epr_sockets:
            return None
        for sck in self._epr_sockets[app_id]:
            if sck.socket_id == sck_id and sck.remote_id == rem_id:
                return sck
        return None

    def put_create_ck_request(
        self, req: NetstackCreateRequest, request: ReqCreateAndKeep
    ) -> Generator[EventExpression, None, None]:
        num_pairs = request.number

        self._send_peer_msg(request)
        peer_msg = yield from self._receive_peer_msg()
        self._logger.debug(f"received peer msg: {peer_msg}")

        self._logger.info(f"putting CK request to EGP for {num_pairs} pairs")
        self._logger.info(f"splitting request into {num_pairs} 1-pair requests")
        request.number = 1

        for pair_index in range(num_pairs):
            self._logger.info(f"trying to allocate comm qubit for pair {pair_index}")
            while True:
                try:
                    phys_id = self.physical_memory.allocate_comm()
                    break
                except AllocError:
                    self._logger.info("no comm qubit available, waiting...")
                    yield self.await_signal(
                        sender=self._qnos.processor, signal_label="memory free"
                    )  # TODO
                    self._logger.info(
                        "a 'free' happened, trying again to allocate comm qubit..."
                    )
            self._logger.info(f"putting CK request for pair {pair_index}")
            self._egp.put(request)

            self._logger.info(f"waiting for result for pair {pair_index}")
            yield self.await_signal(
                sender=self._egp, signal_label=ResCreateAndKeep.__name__
            )
            result: ResCreateAndKeep = self._egp.get_signal_result(
                ResCreateAndKeep.__name__, receiver=self
            )
            self._logger.info(f"got result for pair {pair_index}: {result}")

            if result.bell_state == BellIndex.B00:
                pass
            elif result.bell_state == BellIndex.B01:
                prog = QuantumProgram()
                prog.apply(INSTR_ROT_X, qubit_indices=[0], angle=PI)
                yield self.qdevice.execute_program(prog)
            elif result.bell_state == BellIndex.B10:
                prog = QuantumProgram()
                prog.apply(INSTR_ROT_Z, qubit_indices=[0], angle=PI)
                yield self.qdevice.execute_program(prog)
            elif result.bell_state == BellIndex.B11:
                prog = QuantumProgram()
                prog.apply(INSTR_ROT_X, qubit_indices=[0], angle=PI)
                prog.apply(INSTR_ROT_Z, qubit_indices=[0], angle=PI)
                yield self.qdevice.execute_program(prog)

            app_mem = self.app_memories[req.app_id]
            virt_id = app_mem.get_array_value(req.qubit_array_addr, pair_index)
            app_mem.map_virt_id(virt_id, phys_id)
            self._logger.info(
                f"mapping virtual qubit {virt_id} to physical qubit {phys_id}"
            )

            for i in range(10):
                value = -1
                if i == 9:
                    value = result.bell_state
                arr_index = 10 * pair_index + i
                app_mem.set_array_value(req.result_array_addr, arr_index, value)
            self._logger.debug(
                f"wrote to @{req.result_array_addr}[{10 * pair_index}:"
                f"{10 * pair_index + 10}] for app ID {req.app_id}"
            )
            self._send_processor_msg("wrote to array")

    def put_create_md_request(
        self, req: NetstackCreateRequest, request: ReqMeasureDirectly
    ) -> Generator[EventExpression, None, None]:
        phys_id = self.physical_memory.allocate_comm()

        self._send_peer_msg(request)
        peer_msg = yield from self._receive_peer_msg()
        self._logger.info(f"received peer msg: {peer_msg}")

        self._egp.put(request)
        yield self.await_signal(
            sender=self._egp, signal_label=ResMeasureDirectly.__name__
        )
        result: ResMeasureDirectly = self._egp.get_signal_result(
            ResMeasureDirectly.__name__, receiver=self
        )
        self._logger.debug(f"bell index: {result.bell_state}")
        self.physical_memory.free(phys_id)

        app_mem = self.app_memories[req.app_id]
        for i in range(10):
            value = -1
            if i == 2:
                value = result.measurement_outcome
            elif i == 3:
                value = result.measurement_basis.value
            elif i == 9:
                value = result.bell_state.value
            app_mem.set_array_value(req.result_array_addr, i, value)

        self._send_processor_msg("wrote to array")

    def put_create_request(
        self, req: NetstackCreateRequest
    ) -> Generator[EventExpression, None, None]:
        assert (
            self.find_epr_socket(req.app_id, req.epr_socket_id, req.remote_node_id)
            is not None
        )
        args = self._read_request_args_array(req.app_id, req.arg_array_addr)
        request = self._construct_request(req.remote_node_id, args)
        if isinstance(request, ReqCreateAndKeep):
            yield from self.put_create_ck_request(req, request)
        elif isinstance(request, ReqMeasureDirectly):
            yield from self.put_create_md_request(req, request)

    def put_receive_ck_request(
        self, req: NetstackReceiveRequest, request: ReqCreateAndKeep
    ) -> Generator[EventExpression, None, None]:
        assert isinstance(request, ReqCreateAndKeep)
        num_pairs = request.number

        self._logger.debug("sending 'ready' to peer")
        self._send_peer_msg("ready")

        self._logger.info(f"putting CK request to EGP for {num_pairs} pairs")
        self._logger.info(f"splitting request into {num_pairs} 1-pair requests")
        request.number = 1

        for pair_index in range(num_pairs):
            self._logger.info(f"trying to allocate comm qubit for pair {pair_index}")
            while True:
                try:
                    phys_id = self.physical_memory.allocate_comm()
                    break
                except AllocError:
                    self._logger.info("no comm qubit available, waiting...")
                    yield self.await_signal(
                        sender=self._qnos.processor, signal_label="memory free"
                    )  # TODO
                    self._logger.info(
                        "a 'free' happened, trying again to allocate comm qubit..."
                    )
            self._logger.info(f"putting CK request for pair {pair_index}")
            self._egp.put(ReqReceive(remote_node_id=req.remote_node_id))
            self._logger.info(f"waiting for result for pair {pair_index}")

            yield self.await_signal(
                sender=self._egp, signal_label=ResCreateAndKeep.__name__
            )
            result: ResCreateAndKeep = self._egp.get_signal_result(
                ResCreateAndKeep.__name__, receiver=self
            )
            self._logger.info(f"got result for pair {pair_index}: {result}")

            app_mem = self.app_memories[req.app_id]
            virt_id = app_mem.get_array_value(req.qubit_array_addr, pair_index)
            app_mem.map_virt_id(virt_id, phys_id)
            self._logger.info(
                f"mapping virtual qubit {virt_id} to physical qubit {phys_id}"
            )

            for i in range(10):
                value = -1
                if i == 9:
                    value = result.bell_state.value
                arr_index = 10 * pair_index + i
                app_mem.set_array_value(req.result_array_addr, arr_index, value)
            self._logger.debug(
                f"wrote to @{req.result_array_addr}[{10 * pair_index}:"
                f"{10 * pair_index + 10}] for app ID {req.app_id}"
            )
            self._send_processor_msg("wrote to array")

    def put_receive_md_request(
        self, req: NetstackReceiveRequest, request: ReqMeasureDirectly
    ) -> Generator[EventExpression, None, None]:
        assert isinstance(request, ReqMeasureDirectly)

        phys_id = self.physical_memory.allocate_comm()

        self._egp.put(ReqReceive(remote_node_id=req.remote_node_id))
        self._logger.debug("sending 'ready' to peer")
        self._send_peer_msg("ready")

        yield self.await_signal(
            sender=self._egp, signal_label=ResMeasureDirectly.__name__
        )
        result: ResMeasureDirectly = self._egp.get_signal_result(
            ResMeasureDirectly.__name__, receiver=self
        )

        self.physical_memory.free(phys_id)

        app_mem = self.app_memories[req.app_id]
        for i in range(10):
            value = -1
            if i == 2:
                value = result.measurement_outcome
            elif i == 3:
                value = result.measurement_basis.value
            elif i == 9:
                value = result.bell_state.value
            app_mem.set_array_value(req.result_array_addr, i, value)

        self._send_processor_msg("wrote to array")

    def put_receive_request(
        self, req: NetstackReceiveRequest
    ) -> Generator[EventExpression, None, None]:
        assert (
            self.find_epr_socket(req.app_id, req.epr_socket_id, req.remote_node_id)
            is not None
        )

        create_request = yield from self._receive_peer_msg()
        self._logger.debug(f"received {create_request} from peer")
        if isinstance(create_request, ReqCreateAndKeep):
            yield from self.put_receive_ck_request(req, create_request)
        elif isinstance(create_request, ReqMeasureDirectly):
            yield from self.put_receive_md_request(req, create_request)

    def put_breakpoint_create_request(self) -> Generator[EventExpression, None, None]:
        # synchronize with peer
        self._send_peer_msg("breakpoint start")
        response = yield from self._receive_peer_msg()
        assert response == "breakpoint start"
        # peer is now ready
        # notify processor
        self._send_processor_msg("breakpoint ready")
        # wait for processor to be finished
        processor_msg = yield from self._receive_processor_msg()
        assert processor_msg == "breakpoint end"
        # tell peer that breakpoint is finished
        self._send_peer_msg("breakpoint end")
        # wait for peer to have finsihed as well
        response = yield from self._receive_peer_msg()
        assert response == "breakpoint end"
        # notify processor
        self._send_processor_msg("breakpoint finished")

    def put_breakpoint_receive_request(self) -> Generator[EventExpression, None, None]:
        msg = yield from self._receive_peer_msg()
        assert msg == "breakpoint start"
        self._send_peer_msg("breakpoint start")
        # notify processor
        self._send_processor_msg("breakpoint ready")
        # wait for processor to be finished
        processor_msg = yield from self._receive_processor_msg()
        assert processor_msg == "breakpoint end"
        # wait for peer to be finished
        peer_msg = yield from self._receive_peer_msg()
        assert peer_msg == "breakpoint end"
        self._send_peer_msg("breakpoint end")
        # notify processor
        self._send_processor_msg("breakpoint finished")

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            msg = yield from self._receive_processor_msg()
            self._logger.debug(f"received new msg from processor: {msg}")
            if isinstance(msg, NetstackCreateRequest):
                yield from self.put_create_request(msg)
                self._logger.debug("create request done")
            elif isinstance(msg, NetstackReceiveRequest):
                yield from self.put_receive_request(msg)
                self._logger.debug("receive request done")
            elif isinstance(msg, NetstackBreakpointCreateRequest):
                yield from self.put_breakpoint_create_request()
                self._logger.debug("breakpoint create request done")
            elif isinstance(msg, NetstackBreakpointReceiveRequest):
                yield from self.put_breakpoint_receive_request()
                self._logger.debug("breakpoint receive request done")
