from __future__ import annotations

from typing import Any, Callable, Dict, Generator, List, Optional

import netsquid as ns
from netqasm.backend.executor import Executor
from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
    SubroutineMessage,
    deserialize_host_msg,
)
from netqasm.lang.instr import NVFlavour
from netqasm.lang.parsing import deserialize as deser_subroutine
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.shared_memory import SharedMemory
from netsquid.components.component import Port
from netsquid.nodes import Node
from netsquid.protocols import NodeProtocol, Protocol

from pydynaa import EventExpression, EventType
from squidasm.nqasm.executor.nv import NVNetSquidExecutor
from squidasm.nqasm.netstack import NetworkStack
from squidasm.nqasm.singlethread.csocket import NewClasMsgEvent

NewResultEvent: EventType = EventType(
    "NewResultEvent",
    "A new result from QNodeOS has arrived on the Host",
)

NewHostMsgEvent: EventType = EventType(
    "NewHostMsgEvent",
    "A new message from the Host has arrived at QNodeOS",
)

SUBRT_FINISHED = "Subroutine finished"


class QNodeOsProtocol(NodeProtocol):
    def __init__(
        self, node: Node, instr_proc_time: int = 0, host_latency: int = 0
    ) -> None:
        super().__init__(node=node, name=node.name)
        self._executor = NVNetSquidExecutor(
            node=self.node, instr_proc_time=instr_proc_time, host_latency=host_latency
        )
        self.node.add_ports(["host"])
        self._flavour = NVFlavour()

        self._listener = QNodeOsListener(self.node.ports["host"])

    def set_network_stack(self, network_stack: NetworkStack):
        self._executor.network_stack = network_stack

    @property
    def host_port(self) -> Port:
        return self.node.ports["host"]

    @property
    def executor(self) -> Executor:
        return self._executor

    def _receive_msg(self) -> Generator[EventExpression, None, bytes]:
        if len(self._listener.buffer) == 0:
            yield EventExpression(source=self._listener, event_type=NewHostMsgEvent)
        return self._listener.buffer.pop(0)

    def _receive_init_msg(self) -> Generator[EventExpression, None, Subroutine]:
        if len(self._listener.buffer) == 0:
            yield EventExpression(source=self._listener, event_type=NewHostMsgEvent)

        raw_msg = self._listener.buffer.pop(0)
        msg = deserialize_host_msg(raw_msg)
        assert isinstance(msg, InitNewAppMessage)
        self.executor.init_new_application(msg.app_id, msg.max_qubits)

    def _receive_subroutine(self) -> Generator[EventExpression, None, Subroutine]:
        if len(self._listener.buffer) == 0:
            yield EventExpression(source=self._listener, event_type=NewHostMsgEvent)

        raw_msg = self._listener.buffer.pop(0)
        msg = deserialize_host_msg(raw_msg)
        assert isinstance(msg, SubroutineMessage)
        subroutine = deser_subroutine(msg.subroutine, flavour=self._flavour)
        return subroutine

    def run(self) -> Generator[EventExpression, None, None]:
        yield from self._receive_init_msg()

        while self.is_running:
            raw_msg = yield from self._receive_msg()
            msg = deserialize_host_msg(raw_msg)

            if isinstance(msg, InitNewAppMessage):
                self.executor.init_new_application(msg.app_id, msg.max_qubits)
            elif isinstance(msg, OpenEPRSocketMessage):
                yield from self._executor.setup_epr_socket(
                    msg.epr_socket_id, msg.remote_node_id, msg.remote_epr_socket_id
                )
                self.host_port.tx_output(SUBRT_FINISHED)
            elif isinstance(msg, SubroutineMessage):
                subroutine = deser_subroutine(msg.subroutine, flavour=self._flavour)
                yield from self._executor.execute_subroutine(subroutine=subroutine)
                # Tell the host that the subroutine has finished so that it can inspect
                # the shared memory.
                self.host_port.tx_output(SUBRT_FINISHED)
            elif isinstance(msg, StopAppMessage):
                yield from self._executor.stop_application(msg.app_id)
                self.stop()

    def start(self) -> None:
        super().start()
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
        super().stop()


class QNodeOsListener(Protocol):
    def __init__(self, port: Port) -> None:
        self._buffer: List[bytes] = []
        self._port: Port = port

    @property
    def buffer(self) -> List[bytes]:
        return self._buffer

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            yield self.await_port_input(self._port)
            self._buffer += self._port.rx_input().items
            self._schedule_now(NewHostMsgEvent)


class HostProtocol(NodeProtocol):
    def __init__(
        self,
        name: str,
        qnodeos: QNodeOsProtocol,
        entry: Callable,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node=Node(f"host_{name}"), name=name)
        self.node.add_ports(["qnos"])
        self.node.add_ports(["peer"])
        self._qnodeos = qnodeos
        self._result: Optional[Dict] = None

        self._qnos_input_buffer: List[str] = []
        self._cl_input_buffer: List[str] = []

        self._peer_listener = HostPeerListener(self.node.ports["peer"])
        self._results_listener = ResultsListener(self.node.ports["qnos"])

        self._entry = entry
        self._inputs = inputs

    @property
    def qnos_port(self) -> Port:
        return self.node.ports["qnos"]

    @property
    def peer_port(self) -> Port:
        return self.node.ports["peer"]

    @property
    def results_listener(self) -> ResultsListener:
        return self._results_listener

    @property
    def peer_listener(self) -> HostPeerListener:
        return self._peer_listener

    def _send_init_app_msg(self, app_id: int, max_qubits: int) -> None:
        self.qnos_port.tx_output(bytes(InitNewAppMessage(app_id, max_qubits)))

    def _send_text_subroutine(self, text: str) -> None:
        subroutine = parse_text_subroutine(text, flavour=NVFlavour())
        self.qnos_port.tx_output(bytes(SubroutineMessage(subroutine)))

    def _receive_results(self) -> Generator[EventExpression, None, SharedMemory]:
        if len(self._results_listener.buffer) == 0:
            yield EventExpression(
                source=self._results_listener, event_type=NewResultEvent
            )

        msg = self._results_listener.buffer.pop(0)
        assert msg == SUBRT_FINISHED
        shared_memory = self._qnodeos.executor._shared_memories[0]
        return shared_memory

    def get_result(self) -> Optional[Dict]:
        return self._result

    def _send_classical(self, text: str) -> None:
        print(f"Sending msg {text} at time {ns.sim_time()}")
        self.peer_port.tx_output(text)

    def start(self) -> None:
        super().start()
        self._peer_listener.start()
        self._results_listener.start()

    def stop(self) -> None:
        self._results_listener.stop()
        self._peer_listener.stop()
        super().stop()

    def _recv_classical(self) -> Generator[EventExpression, None, str]:
        if len(self._peer_listener.buffer) == 0:
            yield EventExpression(
                source=self._peer_listener, event_type=NewClasMsgEvent
            )
        return self._peer_listener.buffer.pop(0)

    def run(self) -> Generator[EventExpression, None, None]:
        if self._inputs:
            self._result = yield from self._entry(self._inputs)
        else:
            self._result = yield from self._entry()


class HostPeerListener(Protocol):
    def __init__(self, port: Port) -> None:
        self._buffer: List[str] = []
        self._port: Port = port

    @property
    def buffer(self) -> List[str]:
        return self._buffer

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            yield self.await_port_input(self._port)
            self._buffer += self._port.rx_input().items
            self._schedule_now(NewClasMsgEvent)


class ResultsListener(Protocol):
    def __init__(self, port: Port) -> None:
        self._buffer: List[str] = []
        self._port: Port = port

    @property
    def buffer(self) -> List[str]:
        return self._buffer

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            yield self.await_port_input(self._port)
            self._buffer += self._port.rx_input().items
            self._schedule_now(NewResultEvent)
