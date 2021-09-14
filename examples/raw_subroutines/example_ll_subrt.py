import logging
import time
from typing import Generator

import netsquid as ns
from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netsquid.components import ClassicalChannel
from netsquid.nodes.connections import DirectConnection

from pydynaa import EventExpression
from squidasm.run.singlethread.protocols import HostProtocol, QNodeOsProtocol
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.nqasm.netstack import NetworkStack

NUM_PAIRS = 20


class AliceProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._send_init_app_msg(app_id=app_id, max_qubits=1)
        yield from self._qnodeos.executor.setup_epr_socket(0, 1 - self.node.ID, 0)

        subroutine = f"""
# NETQASM 1.0
# APPID 0
array {NUM_PAIRS} @0
array {NUM_PAIRS * 10} @1
array {NUM_PAIRS} @2
set R0 0
LOOP3:
beq R0 {NUM_PAIRS} LOOP_EXIT3
store 0 @2[R0]
add R0 R0 1
jmp LOOP3
LOOP_EXIT3:
array 20 @3
store 0 @3[0]
store {NUM_PAIRS} @3[1]
create_epr(1,0) 2 3 1
set R0 0
LOOP2:
beq R0 {NUM_PAIRS} LOOP_EXIT2
set R1 0
set R2 0
set R3 0
set R4 0
LOOP:
beq R4 10 LOOP_EXIT
add R1 R1 R0
add R4 R4 1
jmp LOOP
LOOP_EXIT:
add R2 R0 1
set R4 0
LOOP1:
beq R4 10 LOOP_EXIT1
add R3 R3 R2
add R4 R4 1
jmp LOOP1
LOOP_EXIT1:
wait_all @1[R1:R3]
load Q0 @2[R0]
meas Q0 M0
qfree Q0
store M0 @0[R0]
add R0 R0 1
jmp LOOP2
LOOP_EXIT2:
ret_arr @0
ret_arr @1
ret_arr @2
ret_arr @3
"""
        self._send_text_subroutine(subroutine)
        results = yield from self._receive_results()
        bit_array = results.get_array_part(0, slice(NUM_PAIRS))
        bits = "".join([str(bit) for bit in bit_array])
        print(f"Alice bits: {bits}")


class BobProtocol(HostProtocol):
    def run(self) -> Generator[EventExpression, None, None]:
        app_id = 0
        self._send_init_app_msg(app_id=app_id, max_qubits=1)
        yield from self._qnodeos.executor.setup_epr_socket(0, 1 - self.node.ID, 0)

        subroutine = f"""
# NETQASM 1.0
# APPID 0
array {NUM_PAIRS} @0
array {NUM_PAIRS * 10} @1
array {NUM_PAIRS} @2
set R0 0
LOOP3:
beq R0 {NUM_PAIRS} LOOP_EXIT3
store 0 @2[R0]
add R0 R0 1
jmp LOOP3
LOOP_EXIT3:
recv_epr(0,0) 2 1
set R0 0
LOOP2:
beq R0 {NUM_PAIRS} LOOP_EXIT2
set R1 0
set R2 0
set R3 0
set R4 0
LOOP:
beq R4 10 LOOP_EXIT
add R1 R1 R0
add R4 R4 1
jmp LOOP
LOOP_EXIT:
add R2 R0 1
set R4 0
LOOP1:
beq R4 10 LOOP_EXIT1
add R3 R3 R2
add R4 R4 1
jmp LOOP1
LOOP_EXIT1:
wait_all @1[R1:R3]
load Q0 @2[R0]
meas Q0 M0
qfree Q0
store M0 @0[R0]
add R0 R0 1
jmp LOOP2
LOOP_EXIT2:
ret_arr @0
ret_arr @1
ret_arr @2
"""
        self._send_text_subroutine(subroutine)
        results = yield from self._receive_results()
        bit_array = results.get_array_part(0, slice(NUM_PAIRS))
        bits = "".join([str(bit) for bit in bit_array])
        print(f"Bob bits  : {bits}")


def main():
    start = time.perf_counter()

    set_log_level(logging.INFO)

    network_cfg = default_network_config(["alice", "bob"], hardware=QuantumHardware.NV)
    network = NetSquidNetwork(network_cfg)

    qnos_alice = QNodeOsProtocol(node=network.get_node("alice"))
    host_alice = AliceProtocol("alice", qnos_alice, None)
    network.add_node(host_alice.node)

    ll_alice = network.link_layer_services["alice"]
    netstack_alice = NetworkStack(node=qnos_alice.node, link_layer_services=ll_alice)
    qnos_alice.set_network_stack(netstack_alice)
    for service in ll_alice.values():
        service.add_reaction_handler(qnos_alice._executor._handle_epr_response)

    conn_alice = DirectConnection(
        name="conn_alice",
        channel_AtoB=ClassicalChannel("chan_host_qnos_alice"),
        channel_BtoA=ClassicalChannel("chan_qnos_host_alice"),
    )
    network.add_subcomponent(conn_alice)

    host_alice.qnos_port.connect(conn_alice.ports["A"])
    qnos_alice.host_port.connect(conn_alice.ports["B"])

    qnos_bob = QNodeOsProtocol(network.get_node("bob"))
    host_bob = BobProtocol("bob", qnos_bob, None)
    network.add_node(host_bob.node)

    ll_bob = network.link_layer_services["bob"]
    netstack_bob = NetworkStack(node=qnos_bob.node, link_layer_services=ll_bob)
    qnos_bob.set_network_stack(netstack_bob)
    for service in ll_bob.values():
        service.add_reaction_handler(qnos_bob._executor._handle_epr_response)

    conn_bob = DirectConnection(
        name="conn_bob",
        channel_AtoB=ClassicalChannel("chan_host_qnos_bob"),
        channel_BtoA=ClassicalChannel("chan_qnos_host_bob"),
    )
    network.add_subcomponent(conn_bob)

    host_bob.qnos_port.connect(conn_bob.ports["A"])
    qnos_bob.host_port.connect(conn_bob.ports["B"])

    host_alice.start()
    qnos_alice.start()
    host_bob.start()
    qnos_bob.start()
    ns.sim_run()

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")


if __name__ == "__main__":
    main()
