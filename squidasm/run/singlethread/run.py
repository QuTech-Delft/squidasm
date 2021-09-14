import itertools
import os
import pathlib
from typing import Any, Callable, Dict, List, Optional, Tuple

import netsquid as ns
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from squidasm.nqasm.netstack import NetworkStack
from squidasm.run.singlethread.context import NetSquidContext
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sim.network import reset_network
from squidasm.sim.network.network import NetSquidNetwork

from . import util


def _setup_connections(
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


def _setup_network_stacks(
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
    """Simulate an application represented by NetSquid Protocols."""

    # `results` is list of `round results`.
    # A `round result` is a list of outputs (dicts) per node.
    results: List[List[Dict]] = []

    for i in range(num):
        print(f"iteration {i}")
        SharedMemoryManager.reset_memories()
        reset_network()

        for host, qnos in protocols:
            qnos.start()
            host.start()

        ns.sim_run()

        round_results: List[Dict] = []
        for host, _ in protocols:
            round_results.append(host.get_result())  # type: ignore
        results.append(round_results)

        for host, qnos in protocols:
            qnos.stop()
            host.stop()

    return results


def run_programs(
    num: int,
    network: NetSquidNetwork,
    programs: Dict[str, Callable],
    inputs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[List[Dict]]:
    """Simulate an application represented by functions."""
    protocols: List[Tuple[HostProtocol, QNodeOsProtocol]] = []

    for name, code in programs.items():
        # for now, classical communication latencies are mocked in the Executor itself
        qnos = QNodeOsProtocol(
            node=network.get_node(name),
            instr_proc_time=network.instr_proc_time,
            host_latency=network.host_latency,
        )
        input = inputs.get(name, {}) if inputs else None
        host = HostProtocol(name, qnos, code, input)
        network.add_node(host.node)
        protocols.append((host, qnos))
        NetSquidContext.add_protocol(name, host)

    _setup_connections(network, protocols)
    _setup_network_stacks(network, protocols)

    return run_protocols(num, protocols)


def run_files(
    num: int,
    network: NetSquidNetwork,
    filenames: Dict[str, str],
    inputs: Optional[Dict[str, Dict[str, Any]]] = None,
    insert_yields=False,
) -> List[List[Dict]]:
    """Simulate an application represented by source files."""
    programs: Dict[str, Callable] = {}

    for name, filename in filenames.items():
        if insert_yields:
            # Add `yield from` to flush() and classical recv() statements.
            module = str(pathlib.Path(filename).with_suffix("")).replace(os.sep, ".")
            module = util.modify_and_import(module, None)
            code = getattr(module, "main")
        else:
            code = util.load_program(filename)

        programs[name] = code

    return run_programs(num, network, programs, inputs)
