import logging
import math
import time
from typing import Dict, Generator, List, Tuple

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression, EventHandler, EventType
from squidasm.run.singlethread import NetQASMConnection, NetSquidContext, Socket
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.run.singlethread.csocket import NetSquidSocket as Socket
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


def client_main():
    epr_socket = EPRSocket("server")

    client = NetQASMConnection("client", epr_sockets=[epr_socket])
    socket = Socket("client", "server")

    with client:
        e = epr_socket.create(1)[0]
        m1 = e.measure()
        msg = yield from socket.recv()
        print(f"received: {msg}")
        yield from client.flush()

    m1 = int(m1)
    return {"m1": m1}


def server_main():
    epr_socket = EPRSocket("client")

    server = NetQASMConnection("server", epr_sockets=[epr_socket])
    socket = Socket("server", "client")

    with server:
        e = epr_socket.recv(1)[0]
        m1 = e.measure()
        socket.send("hello")
        yield from server.flush()

    m1 = int(m1)
    return {"m1": m1}


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        self._result = yield from client_main()


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        self._result = yield from server_main()


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

    NetSquidContext._nodes = {0: "client", 1: "server"}
    NetSquidContext._protocols = {"client": host_client, "server": host_server}

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

    num = 1

    results: List[Tuple[Dict, Dict]] = []

    for i in range(num):
        print(f"iteration {i}")
        SharedMemoryManager.reset_memories()
        results.append(main())

    print(results)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
