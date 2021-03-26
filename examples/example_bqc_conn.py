import logging
import math
import time
from typing import Dict, Generator, List, Optional, Tuple

import netsquid as ns
from netqasm.backend.executor import Executor
from netqasm.backend.messages import SubroutineMessage, deserialize_host_msg
from netqasm.lang.instr import NVFlavour
from netqasm.lang.parsing import deserialize as deser_subroutine
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.components.component import Port
from netsquid.nodes import Node
from netsquid.nodes.connections import DirectConnection
from netsquid.protocols import NodeProtocol, Protocol

from pydynaa import EventExpression, EventType
from squidasm.sdk.socket import NetSquidSocket as Socket
from squidasm.sdk.socket import NewClasMsgEvent
from squidasm.sdk.sthread import SThreadNetSquidConnection
from squidasm.sim.executor.nv import NVNetSquidExecutor
from squidasm.sim.network.network import NetSquidNetwork
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


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._qnodeos.executor.init_new_application(app_id=app_id, max_qubits=2)
        yield from self._qnodeos.executor.setup_epr_socket(0, 1, 0)

        epr_socket = EPRSocket("server")
        epr_socket._conn = self._conn
        epr_socket._remote_node_id = 1

        socket = Socket("client", "server", self, self.peer_port)

        alpha = 0
        beta = 0
        theta1 = 0
        theta2 = 0
        r1 = 0
        r2 = 0
        trap = False

        with self._conn as client:
            epr1 = epr_socket.create()[0]

            # RSP
            if trap and dummy == 2:
                # remotely-prepare a dummy state
                p2 = epr1.measure(store_array=False)
            else:
                epr1.rot_Z(angle=theta2)
                epr1.H()
                p2 = epr1.measure(store_array=False)

            # Create EPR pair
            epr2 = epr_socket.create()[0]

            # RSP
            if trap and dummy == 1:
                # remotely-prepare a dummy state
                p1 = epr2.measure(store_array=False)
            else:
                epr2.rot_Z(angle=theta1)
                epr2.H()
                p1 = epr2.measure(store_array=False)
            client.flush()

            results = yield from self._receive_results()
            p1 = results.get_register("M0")
            p2 = results.get_register("M1")
            p1 = int(p1)
            p2 = int(p2)

            if trap and dummy == 2:
                delta1 = -theta1 + (p1 + r1) * math.pi
            else:
                delta1 = alpha - theta1 + (p1 + r1) * math.pi
            socket.send(str(delta1))

            m1 = yield from socket.recv()
            m1 = int(m1)
            if trap and dummy == 1:
                delta2 = -theta2 + (p2 + r2) * math.pi
            else:
                delta2 = math.pow(-1, (m1 + r1)) * beta - theta2 + (p2 + r2) * math.pi
            socket.send(str(delta2))

        self._result = {"p1": p1, "p2": p2}


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._qnodeos.executor.init_new_application(app_id=app_id, max_qubits=2)
        yield from self._qnodeos.executor.setup_epr_socket(0, 0, 0)

        epr_socket = EPRSocket("client")
        epr_socket._conn = self._conn
        epr_socket._remote_node_id = 0

        socket = Socket("server", "client", self, self.peer_port)

        with self._conn as server:
            epr1 = epr_socket.recv()[0]
            epr2 = epr_socket.recv()[0]

            epr2.cphase(epr1)
            server.flush()
            yield from self._receive_results()

            delta1 = yield from socket.recv()
            delta1 = float(delta1)

            epr2.rot_Z(angle=delta1)
            epr2.H()
            m1 = epr2.measure(store_array=False)
            server.flush()

            results = yield from self._receive_results()
            m1 = results.get_register("M0")

            socket.send(str(m1))

            delta2 = yield from socket.recv()
            delta2 = float(delta2)

            epr1.rot_Z(angle=delta2)
            epr1.H()
            m2 = epr1.measure(store_array=False)
            server.flush()

            results = yield from self._receive_results()
            m2 = results.get_register("M0")

        m1, m2 = int(m1), int(m2)
        self._result = {"m1": m1, "m2": m2}


def main():
    # set_log_level(logging.DEBUG)
    # set_log_level(logging.INFO)
    set_log_level(logging.WARNING)

    network_cfg = default_network_config(
        ["client", "server"], hardware=QuantumHardware.NV
    )
    network = NetSquidNetwork(network_cfg)

    qnos_client = QNodeOsProtocol(node=network.get_node("client"))
    host_client = ClientProtocol("client", qnos_client)
    network.add_node(host_client.node)

    ll_client = network.link_layer_services["client"]
    netstack_client = NetworkStack(node=qnos_client.node, link_layer_services=ll_client)
    qnos_client.set_network_stack(netstack_client)
    for service in ll_client.values():
        service.add_reaction_handler(qnos_client._executor._handle_epr_response)

    conn_client = DirectConnection(
        name="conn_client",
        channel_AtoB=ClassicalChannel("chan_host_qnos_client"),
        channel_BtoA=ClassicalChannel("chan_qnos_host_client"),
    )
    network.add_subcomponent(conn_client)

    host_client.qnos_port.connect(conn_client.ports["A"])
    qnos_client.host_port.connect(conn_client.ports["B"])

    qnos_server = QNodeOsProtocol(network.get_node("server"))
    host_server = ServerProtocol("server", qnos_server)
    network.add_node(host_server.node)

    ll_server = network.link_layer_services["server"]
    netstack_server = NetworkStack(node=qnos_server.node, link_layer_services=ll_server)
    qnos_server.set_network_stack(netstack_server)
    for service in ll_server.values():
        service.add_reaction_handler(qnos_server._executor._handle_epr_response)

    conn_server = DirectConnection(
        name="conn_server",
        channel_AtoB=ClassicalChannel("chan_host_qnos_server"),
        channel_BtoA=ClassicalChannel("chan_qnos_host_server"),
    )
    network.add_subcomponent(conn_server)

    host_server.qnos_port.connect(conn_server.ports["A"])
    qnos_server.host_port.connect(conn_server.ports["B"])

    conn_client_server = DirectConnection(
        name="conn_client_server",
        channel_AtoB=ClassicalChannel("chan_client_server"),
        channel_BtoA=ClassicalChannel("chan_server_client"),
    )
    network.add_subcomponent(conn_client_server)

    host_client.peer_port.connect(conn_client_server.ports["A"])
    host_server.peer_port.connect(conn_client_server.ports["B"])

    host_client.start()
    qnos_client.start()
    host_server.start()
    qnos_server.start()

    ns.sim_run()

    host_client.stop()
    qnos_client.stop()
    host_server.stop()
    qnos_server.stop()

    ns.sim_reset()

    client_results = host_client.get_result()
    # print(f"client results: {client_results}")
    server_results = host_server.get_result()
    # print(f"server results: {server_results}")

    return client_results, server_results


if __name__ == "__main__":
    start = time.perf_counter()

    num = 100

    results: List[Tuple[Dict, Dict]] = []

    for _ in range(num):
        SharedMemoryManager.reset_memories()
        results.append(main())

    print(results)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
