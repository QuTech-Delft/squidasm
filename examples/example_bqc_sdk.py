import ast
import importlib
import inspect
import logging
import time
from typing import Callable, Dict, Generator, List, Tuple

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression
from squidasm.run.singlethread import NetSquidContext
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sim.network import reset_network
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


class _AddYieldFrom(ast.NodeTransformer):
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
    tree = _AddYieldFrom().visit(tree)
    recompiled = compile(tree, "<ast>", "exec")

    exec(recompiled, globals(), locals())

    gen = locals()["_compiled_as_generator"]
    return gen


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        self._result = yield from self._entry()


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
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

    spec = importlib.util.spec_from_file_location(
        "client", "examples/apps/bqc_5_6/app_client.py"
    )
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    bqc_client = getattr(client, "main")

    # client_generator = make_generator(bqc_client)
    qnos_client = QNodeOsProtocol(node=network.get_node("client"))
    host_client = ClientProtocol("client", qnos_client, bqc_client)
    network.add_node(host_client.node)

    spec = importlib.util.spec_from_file_location(
        "server", "examples/apps/bqc_5_6/app_server.py"
    )
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    bqc_server = getattr(server, "main")

    # server_generator = make_generator(bqc_server)
    qnos_server = QNodeOsProtocol(network.get_node("server"))
    host_server = ServerProtocol("server", qnos_server, bqc_server)
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

    results = main(num=10)
    print(results)
    m2_0_count = len([r for r in results if r[1]["m2"] == 0])
    print(m2_0_count)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
