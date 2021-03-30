import logging
import math
import time
from typing import Dict, Generator, List, Tuple

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression, EventHandler, EventType
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.run.singlethread.csocket import NetSquidSocket as Socket
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


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
        dummy = 0

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

            # msg = yield from socket.recv()
            msg = socket.recv()
            m1 = int(msg)
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

            # msg = yield from socket.recv()
            msg = socket.recv()
            delta1 = float(msg)

            epr2.rot_Z(angle=delta1)
            epr2.H()
            m1 = epr2.measure(store_array=False)
            server.flush()

            results = yield from self._receive_results()
            m1 = results.get_register("M0")

            socket.send(str(m1))

            # msg = yield from socket.recv()
            msg = socket.recv()
            delta2 = float(msg)

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

    num = 1

    results: List[Tuple[Dict, Dict]] = []

    for i in range(num):
        print(f"iteration {i}")
        SharedMemoryManager.reset_memories()
        results.append(main())

    print(results)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
