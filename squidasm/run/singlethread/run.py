import importlib
import itertools
import os
import pathlib
import re
import sys
from typing import Callable, Dict, List, Tuple

import netsquid as ns
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

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


def run_protocols(
    num: int, protocols: List[Tuple[HostProtocol, QNodeOsProtocol]]
) -> List[List[Dict]]:
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
            round_results.append(host.get_result())  # type: ignore
        results.append(round_results)

        for host, qnos in protocols:
            host.stop()
            qnos.stop()

    return results


def _load_program(filename: str) -> Callable:
    spec = importlib.util.spec_from_file_location("module", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    func = getattr(module, "main")
    return func  # type: ignore


def _modify_and_import(module_name, package):
    spec = importlib.util.find_spec(module_name, package)
    source = spec.loader.get_source(module_name)
    lines = source.splitlines()
    new_lines = []
    socket_name = None
    epr_socket_name = None
    for line in lines:
        new_lines.append(line)
        sck_result = re.search(r" (\w+) = Socket\(", line)
        epr_result = re.search(r" (\w+) = EPRSocket\(", line)
        if sck_result is not None:
            socket_name = sck_result.group(1)
        if epr_result is not None:
            epr_socket_name = epr_result.group(1)
        if socket_name is None and epr_socket_name is None:
            continue
        if re.search(fr"{socket_name}\.recv\(\)", line) and not re.search(
            fr"{epr_socket_name}\.recv\(\)", line
        ):
            new_line = re.sub(
                fr"{socket_name}.recv\(\)", f"(yield from {socket_name}.recv())", line
            )
            new_lines[-1] = new_line
        if re.search(r"\w+\.flush\(\)", line):
            new_line = re.sub(r"(\w+\.flush\(\))", r"(yield from \1)", line)
            new_lines[-1] = new_line

    new_source = "\n".join(new_lines)
    module = importlib.util.module_from_spec(spec)
    codeobj = compile(new_source, module.__spec__.origin, "exec")
    exec(codeobj, module.__dict__)
    sys.modules[module_name] = module
    return module


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

    return run_protocols(num, protocols)


def run_files(
    num: int, network: NetSquidNetwork, filenames: Dict[str, str], insert_yields=False
) -> List[List[Dict]]:
    programs: Dict[str, Callable] = {}

    for name, filename in filenames.items():
        if insert_yields:
            module = str(pathlib.Path(filename).with_suffix("")).replace(os.sep, ".")
            module = _modify_and_import(module, None)
            code = getattr(module, "main")
        else:
            code = _load_program(filename)

        programs[name] = code

    return run_programs(num, network, programs)
