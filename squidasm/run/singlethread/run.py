import ast
import importlib
import inspect
import itertools
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
from squidasm.run.singlethread.context import NetSquidContext
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sim.network import reset_network
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.stack import NetworkStack


def setup_connections(
    network: NetSquidNetwork,
    protocols: List[Tuple[HostProtocol, QNodeOsProtocol]],
) -> None:
    # Host <-> QNodeOS connections
    for host, qnos in protocols:
        conn = DirectConnection(
            name=f"conn_{host.name}",
            channel_AtoB=ClassicalChannel(f"chan_host_qnos_{host.name}"),
            channel_BtoA=ClassicalChannel(f"chan_qnos_host_{host.name}"),
        )
        network.add_subcomponent(conn)
        host.qnos_port.connect(conn.ports["A"])
        qnos.host_port.connect(conn.ports["B"])

    # Host <-> Host connections
    for (host1, _), (host2, _) in itertools.combinations(protocols, 2):
        conn = DirectConnection(
            name=f"conn_{host1.name}_{host2.name}",
            channel_AtoB=ClassicalChannel(f"chan_{host1.name}_{host2.name}"),
            channel_BtoA=ClassicalChannel(f"chan_{host2.name}_{host1.name}"),
        )
        network.add_subcomponent(conn)
        host1.peer_port.connect(conn.ports["A"])
        host2.peer_port.connect(conn.ports["B"])


def setup_network_stacks(
    network: NetSquidNetwork, protocols: List[Tuple[HostProtocol, QNodeOsProtocol]]
):
    for _, qnos in protocols:
        ll = network.link_layer_services[qnos.name]
        netstack = NetworkStack(node=qnos.node, link_layer_services=ll)
        qnos.set_network_stack(netstack)
        for service in ll.values():
            service.add_reaction_handler(qnos._executor._handle_epr_response)


def run_netsquid(
    num: int, protocols: List[Tuple[HostProtocol, QNodeOsProtocol]]
) -> List[Tuple[Dict, Dict]]:
    # results is list of round results
    # round result is a list of outputs (dicts) per node
    results: List[List[Dict]] = []

    for i in range(num):
        print(f"iteration {i}")
        SharedMemoryManager.reset_memories()
        reset_network()

        for host, qnos in protocols:
            host.start()
            qnos.start()

        ns.sim_run()

        round_results: List[Dict] = []
        for host, _ in protocols:
            round_results.append(host.get_result())
        results.append(round_results)

        for host, qnos in protocols:
            host.stop()
            qnos.stop()

    return results


def run_programs(
    num: int, network: NetSquidNetwork, programs: Dict[str, Callable]
) -> List[List[Dict]]:
    protocols: List[Tuple[HostProtocol, QNodeOsProtocol]] = []

    for name, code in programs.items():
        # generator = make_generator(code)
        qnos = QNodeOsProtocol(node=network.get_node(name))
        host = HostProtocol(name, qnos, code)
        network.add_node(host.node)
        protocols.append((host, qnos))
        NetSquidContext()._protocols[name] = host

    setup_connections(network, protocols)
    setup_network_stacks(network, protocols)

    NetSquidContext._nodes = {0: "client", 1: "server"}

    return run_netsquid(num, protocols)


def main(num: int) -> List[List[Dict]]:
    # set_log_level(logging.DEBUG)
    # set_log_level(logging.INFO)
    set_log_level(logging.WARNING)

    network_cfg = default_network_config(
        ["client", "server"], hardware=QuantumHardware.NV
    )
    network = NetSquidNetwork(network_cfg)

    spec = importlib.util.spec_from_file_location(
        "server", "examples/apps/bqc_5_6/app_server.py"
    )
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    bqc_server = getattr(server, "main")

    spec = importlib.util.spec_from_file_location(
        "client", "examples/apps/bqc_5_6/app_client.py"
    )
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    bqc_client = getattr(client, "main")

    return run_programs(
        num=num, network=network, programs={"client": bqc_client, "server": bqc_server}
    )


if __name__ == "__main__":
    start = time.perf_counter()

    results = main(num=10)
    print(results)
    m2_0_count = len([r for r in results if r[1]["m2"] == 0])
    print(m2_0_count)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
