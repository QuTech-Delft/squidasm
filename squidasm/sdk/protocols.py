from typing import Dict, Generator, List, Optional

import netsquid as ns
from netqasm.backend.executor import Executor
from netqasm.backend.messages import SubroutineMessage, deserialize_host_msg
from netqasm.lang.instr import NVFlavour
from netqasm.lang.parsing import deserialize as deser_subroutine
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.shared_memory import SharedMemory
from netsquid.components.component import Port
from netsquid.nodes import Node
from netsquid.protocols import NodeProtocol, Protocol

from pydynaa import EventExpression
from squidasm.sdk.socket import NewClasMsgEvent
from squidasm.sdk.sthread import SThreadNetSquidConnection
from squidasm.sim.executor.nv import NVNetSquidExecutor
from squidasm.sim.network.stack import NetworkStack


class QNodeOsProtocol(NodeProtocol):
    def __init__(self, node: Node) -> None:
        super().__init__(node=node)
        self._executor = NVNetSquidExecutor(node=self.node)
        self.node.add_ports(["host"])
        self._flavour = NVFlavour()

    def set_network_stack(self, network_stack: NetworkStack):
        self._executor.network_stack = network_stack

    @property
    def host_port(self) -> Port:
        return self.node.ports["host"]

    @property
    def executor(self) -> Executor:
        return self._executor

    def _receive_subroutine(self) -> Generator[EventExpression, None, Subroutine]:
        yield self.await_port_input(self.host_port)
        raw_msg = self.host_port.rx_input().items[0]
        msg = deserialize_host_msg(raw_msg)
        assert isinstance(msg, SubroutineMessage)
        subroutine = deser_subroutine(msg.subroutine, flavour=self._flavour)
        return subroutine

    def run(self) -> Generator[EventExpression, None, None]:
        while self.is_running:
            # Wait for a subroutine from the Host.
            subroutine = yield from self._receive_subroutine()

            # Execute the subroutine.
            yield from self._executor.execute_subroutine(subroutine=subroutine)

            # Tell the host that the subroutine has finished so that it can inspect
            # the shared memory.
            self.host_port.tx_output("done")


class HostProtocol(NodeProtocol):
    def __init__(self, name: str, qnodeos: QNodeOsProtocol) -> None:
        super().__init__(node=Node(f"host_{name}"))
        self.node.add_ports(["qnos"])
        self.node.add_ports(["peer"])
        self._qnodeos = qnodeos
        self._result: Optional[Dict] = None

        self._qnos_input_buffer: List[str] = []
        self._cl_input_buffer: List[str] = []

        self._listener = HostListener(self.node.ports["peer"])

        self._conn: SThreadNetSquidConnection = SThreadNetSquidConnection(
            app_name="name",
            qnos_port=self.node.ports["qnos"],
            compiler=NVSubroutineCompiler,
            executor=qnodeos._executor,
        )

    @property
    def qnos_port(self) -> Port:
        return self.node.ports["qnos"]

    @property
    def peer_port(self) -> Port:
        return self.node.ports["peer"]

    def _send_text_subroutine(self, text: str) -> None:
        subroutine = parse_text_subroutine(text, flavour=NVFlavour())
        self.qnos_port.tx_output(bytes(SubroutineMessage(subroutine)))

    def _receive_results(self) -> Generator[EventExpression, None, SharedMemory]:
        if len(self._qnos_input_buffer) == 0:
            yield self.await_port_input(self.qnos_port)
            self._qnos_input_buffer = self.qnos_port.rx_input().items
        msg = self._qnos_input_buffer.pop(0)
        assert msg == "done"
        shared_memory = self._qnodeos.executor._shared_memories[0]
        return shared_memory

    def get_result(self) -> Optional[Dict]:
        return self._result

    def _send_classical(self, text: str) -> None:
        print(f"Sending msg {text} at time {ns.sim_time()}")
        self.peer_port.tx_output(text)

    def start(self) -> None:
        super().start()
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
        super().stop()

    def _recv_classical(self) -> Generator[EventExpression, None, str]:
        if len(self._listener._buffer) == 0:
            yield EventExpression(event_type=NewClasMsgEvent)
        return self._listener._buffer.pop(0)


class HostListener(Protocol):
    def __init__(self, port: Port) -> None:
        self._buffer: List[str] = []
        self._port: Port = port

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            yield self.await_port_input(self._port)
            self._buffer += self._port.rx_input().items
            self._schedule_now(NewClasMsgEvent)
