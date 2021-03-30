import ast
import inspect
import logging
import math
import re
import time
from collections import defaultdict
from typing import Callable, Dict, Generator, List, Tuple

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection
from netsquid.nodes.node import Node

from pydynaa import EventExpression, EventHandler, EventType
from squidasm.run.ns_sthread import NetQASMConnection, NetSquidContext, Socket
from squidasm.sdk.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sdk.socket import NetSquidSocket as Socket
from squidasm.sim.network import reset_network
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


class AddYieldFrom(ast.NodeTransformer):
    def visit_Call(self, node):
        if hasattr(node.func, "attr"):
            if (
                node.func.attr in ["recv", "flush"]
                and node.func.value.id != "epr_socket"
            ):
                func_call = f"{node.func.value.id}.{node.func.attr}()"
                print(f"NOTE: rewriting '{func_call}' to 'yield from {func_call}'")
                new_node = ast.YieldFrom(node)
                ast.copy_location(new_node, node)
                ast.fix_missing_locations(new_node)
                self.generic_visit(node)
                return new_node
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        new_node = node
        new_node.name = "_compiled_as_generator"
        new_node.decorator_list = []

        ast.copy_location(new_node, node)
        ast.fix_missing_locations(new_node)
        self.generic_visit(node)
        return new_node


def make_generator(func: Callable) -> Generator:
    f = inspect.getsource(func)
    tree = ast.parse(f)
    tree = AddYieldFrom().visit(tree)
    recompiled = compile(tree, "<ast>", "exec")

    exec(recompiled, None, locals())

    gen = locals()["_compiled_as_generator"]
    return gen


def bqc_client(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={
        "alpha": 0,
        "beta": 0,
        "theta1": 0,
        "theta2": 0,
        "r1": 0,
        "r2": 0,
        "trap": False,
        "dummy": 0,
    },
):
    alpha, beta, theta1, theta2, r1, r2 = (
        inputs["alpha"],
        inputs["beta"],
        inputs["theta1"],
        inputs["theta2"],
        inputs["r1"],
        inputs["r2"],
    )

    # Whether it is a trap round or not
    trap = inputs["trap"]

    if trap:
        dummy = inputs["dummy"]

    socket = Socket("client", "server")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("server", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "client",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
    }

    # Initialize the connection
    if not app_config["debug"]:
        client = NetQASMConnection(
            **kwargs,
            addr=app_config["addr"],
            port=app_config["port"],
            dev=app_config["dev"],
        )
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        client = DebugConnection(**kwargs)

    with client:
        # Create EPR pair
        epr1 = epr_socket.create()[0]

        # RSP
        if trap and dummy == 2:
            # remotely-prepare a dummy state
            p2 = epr1.measure(store_array=False)
        else:
            epr1.rot_Z(angle=theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)
        p2 = p2 if not app_config["debug"] else 0

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
        p1 = p1 if not app_config["debug"] else 0
        client.flush()

        p1 = int(p1)
        p2 = int(p2)

        if trap and dummy == 2:
            delta1 = -theta1 + (p1 + r1) * math.pi
        else:
            delta1 = alpha - theta1 + (p1 + r1) * math.pi
        socket.send(str(delta1))

        m1 = socket.recv()
        m1 = int(m1)
        if trap and dummy == 1:
            delta2 = -theta2 + (p2 + r2) * math.pi
        else:
            delta2 = math.pow(-1, (m1 + r1)) * beta - theta2 + (p2 + r2) * math.pi
        socket.send(str(delta2))

    return {"p1": p1, "p2": p2}


def bqc_server(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={},
):

    socket = Socket("server", "client")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("client", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "server",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
    }

    # Initialize the connection
    if not app_config["debug"]:
        server = NetQASMConnection(
            **kwargs,
            addr=app_config["addr"],
            port=app_config["port"],
            dev=app_config["dev"],
        )
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        server = DebugConnection(**kwargs)

    with server:
        # Create EPR Pair
        epr1 = epr_socket.recv()[0]

        epr2 = epr_socket.recv()[0]

        epr2.cphase(epr1)
        server.flush()

        delta1 = float((socket.recv()))

        epr2.rot_Z(angle=delta1)
        epr2.H()
        m1 = epr2.measure(store_array=False)
        m1 = m1 if not app_config["debug"] else 0
        server.flush()

        socket.send(str(m1))

        delta2 = float((socket.recv()))

        epr1.rot_Z(angle=delta2)
        epr1.H()
        m2 = epr1.measure(store_array=False)
        m2 = m2 if not app_config["debug"] else 0
        server.flush()

    m1, m2 = int(m1), int(m2)
    return {"m1": m1, "m2": m2}


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        # gen = make_generator(bqc_client)
        self._result = yield from self._entry()


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        # gen = make_generator(bqc_server)
        self._result = yield from self._entry()


def setup_connections(network, host_client, qnos_client, host_server, qnos_server):
    conn_client = DirectConnection(
        name="conn_client",
        channel_AtoB=ClassicalChannel("chan_host_qnos_client"),
        channel_BtoA=ClassicalChannel("chan_qnos_host_client"),
    )
    network.add_subcomponent(conn_client)

    host_client.qnos_port.connect(conn_client.ports["A"])
    qnos_client.host_port.connect(conn_client.ports["B"])

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


def setup_network_stacks(network, qnos_client, qnos_server):
    ll_client = network.link_layer_services["client"]
    netstack_client = NetworkStack(node=qnos_client.node, link_layer_services=ll_client)
    qnos_client.set_network_stack(netstack_client)
    for service in ll_client.values():
        service.add_reaction_handler(qnos_client._executor._handle_epr_response)

    ll_server = network.link_layer_services["server"]
    netstack_server = NetworkStack(node=qnos_server.node, link_layer_services=ll_server)
    qnos_server.set_network_stack(netstack_server)
    for service in ll_server.values():
        service.add_reaction_handler(qnos_server._executor._handle_epr_response)


def main(num: int) -> List[Tuple[Dict, Dict]]:
    # set_log_level(logging.DEBUG)
    # set_log_level(logging.INFO)
    set_log_level(logging.WARNING)

    network_cfg = default_network_config(
        ["client", "server"], hardware=QuantumHardware.NV
    )
    network = NetSquidNetwork(network_cfg)

    client_generator = make_generator(bqc_client)
    qnos_client = QNodeOsProtocol(node=network.get_node("client"))
    host_client = ClientProtocol("client", qnos_client, client_generator)
    network.add_node(host_client.node)

    server_generator = make_generator(bqc_server)
    qnos_server = QNodeOsProtocol(network.get_node("server"))
    host_server = ServerProtocol("server", qnos_server, server_generator)
    network.add_node(host_server.node)

    setup_connections(network, host_client, qnos_client, host_server, qnos_server)
    setup_network_stacks(network, qnos_client, qnos_server)

    NetSquidContext._nodes = {0: "client", 1: "server"}
    NetSquidContext._protocols = {"client": host_client, "server": host_server}

    results: List[Tuple[Dict, Dict]] = []

    for i in range(num):
        print(f"iteration {i}")
        SharedMemoryManager.reset_memories()
        reset_network()

        host_client.start()
        qnos_client.start()
        host_server.start()
        qnos_server.start()

        ns.sim_run()

        client_results = host_client.get_result()
        server_results = host_server.get_result()
        results.append((client_results, server_results))

        host_client.stop()
        qnos_client.stop()
        host_server.stop()
        qnos_server.stop()

    return results


if __name__ == "__main__":
    start = time.perf_counter()

    results = main(num=100)
    print(results)
    m2_0_count = len([r for r in results if r[1]["m2"] == 0])
    print(m2_0_count)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
