import logging
import time
from typing import Dict, Generator, List, Tuple

from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression
from squidasm.run.singlethread import run_protocols
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.nqasm.netstack import NetworkStack


class ClientProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._send_init_app_msg(app_id=app_id, max_qubits=1)
        yield from self._qnodeos.executor.setup_epr_socket(0, 1, 0)

        subroutine = """
# NETQASM 1.0
# APPID 0
set R0 10
array R0 @0
set R0 1
array R0 @1
set R0 0
set R1 0
store R0 @1[R1]
set R0 20
array R0 @2
set R0 0
set R1 0
store R0 @2[R1]
set R0 1
set R1 1
store R0 @2[R1]
set R0 10
array R0 @3
set R0 1
array R0 @4
set R0 0
set R1 0
store R0 @4[R1]
set R0 20
array R0 @5
set R0 0
set R1 0
store R0 @5[R1]
set R0 1
set R1 1
store R0 @5[R1]
set R0 1
set R1 0
set R2 1
set R3 2
set R4 0
create_epr R0 R1 R2 R3 R4
set R0 0
set R1 10
wait_all @0[R0:R1]
set Q0 0
rot_y Q0 8 4
rot_x Q0 16 4
set Q0 0
meas Q0 M0
qfree Q0
set R0 1
set R1 0
set R2 4
set R3 5
set R4 3
create_epr R0 R1 R2 R3 R4
set R0 0
set R1 10
wait_all @3[R0:R1]
set Q0 0
rot_y Q0 8 4
rot_x Q0 16 4
set Q0 0
meas Q0 M1
qfree Q0
ret_reg M0
ret_reg M1
"""
        self._send_text_subroutine(subroutine)

        results = yield from self._receive_results()
        p1 = results.get_register("M0")
        p2 = results.get_register("M1")
        self._result = {"p1": p1, "p2": p2}


class ServerProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._send_init_app_msg(app_id=app_id, max_qubits=2)
        yield from self._qnodeos.executor.setup_epr_socket(0, 0, 0)

        subrt1 = """
# NETQASM 1.0
# APPID 0
set R0 10
array R0 @0
set R0 1
array R0 @1
set R0 0
set R1 0
store R0 @1[R1]
set R0 10
array R0 @2
set R0 1
array R0 @3
set R0 0
set R1 0
store R0 @3[R1]
set R0 0
set R1 0
set R2 1
set R3 0
recv_epr R0 R1 R2 R3
set R0 0
set R1 10
wait_all @0[R0:R1]
set Q0 1
qalloc Q0
init Q0
set Q0 0
set Q1 1
rot_y Q0 8 4
crot_y Q0 Q1 24 4
rot_x Q0 24 4
crot_x Q0 Q1 8 4
set Q0 0
qfree Q0
set R0 0
set R1 0
set R2 3
set R3 2
recv_epr R0 R1 R2 R3
set R0 0
set R1 10
wait_all @2[R0:R1]
set Q0 0
set Q1 1
rot_y Q1 8 4
crot_x Q0 Q1 8 4
rot_z Q0 24 4
rot_x Q1 24 4
rot_y Q1 24 4
"""
        self._send_text_subroutine(subrt1)
        yield from self._receive_results()

        subrt2 = """
# NETQASM 1.0
# APPID 0
set Q0 0
rot_y Q0 8 4
rot_x Q0 16 4
set Q0 0
meas Q0 M0
qfree Q0
ret_reg M0
"""

        self._send_text_subroutine(subrt2)
        results2 = yield from self._receive_results()
        m1 = results2.get_register("M0")

        subrt3 = """
# NETQASM 1.0
# APPID 0
set Q0 1
rot_y Q0 8 4
rot_x Q0 16 4
set Q0 1
meas Q0 M0
qfree Q0
ret_reg M0
"""

        self._send_text_subroutine(subrt3)
        results3 = yield from self._receive_results()
        m2 = results3.get_register("M0")
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
    host_client = ClientProtocol("client", qnos_client, None)
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
    host_server = ServerProtocol("server", qnos_server, None)
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

    return run_protocols(1, [(host_client, qnos_client), (host_server, qnos_server)])


if __name__ == "__main__":
    start = time.perf_counter()

    num = 1

    results: List[Tuple[Dict, Dict]] = []
    for _ in range(num):
        SharedMemoryManager.reset_memories()
        results.append(main())

    print(results)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")
