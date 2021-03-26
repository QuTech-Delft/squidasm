import logging
import time
from typing import Dict, Generator, List, Tuple

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression
from squidasm.sdk.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sdk.socket import NetSquidSocket
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._qnodeos.executor.init_new_application(app_id=app_id, max_qubits=1)
        yield from self._qnodeos.executor.setup_epr_socket(0, 1, 0)

        socket = NetSquidSocket("client", "server", self, self.peer_port)
        with self._conn:
            socket.send("hello")
        # self._send_classical("hello")


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._qnodeos.executor.init_new_application(app_id=app_id, max_qubits=2)
        yield from self._qnodeos.executor.setup_epr_socket(0, 0, 0)

        socket = NetSquidSocket("server", "client", self, self.peer_port)

        # msg = yield from self._recv_classical()
        with self._conn:
            msg = yield from socket.recv()
            self._result = {"received_msg": msg}


def main():
    # set_log_level(logging.DEBUG)
    set_log_level(logging.INFO)
    # set_log_level(logging.WARNING)

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

    client_results = host_client.get_result()
    # print(f"client results: {client_results}")
    server_results = host_server.get_result()
    # print(f"server results: {server_results}")

    return client_results, server_results


if __name__ == "__main__":
    start = time.perf_counter()

    num = 1

    results: List[Tuple[Dict, Dict]] = []
    for _ in range(num):
        SharedMemoryManager.reset_memories()
        results.append(main())

    print(results)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
