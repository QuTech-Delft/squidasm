import math
from typing import Generator
from typing import Tuple

import netsquid as ns
import netsquid.qubits.qubitapi
from netsquid.components import QuantumProcessor
from netsquid.components.component import Qubit
from netsquid.components.instructions import INSTR_ROT_X, INSTR_ROT_Z, INSTR_ROT_Y, INSTR_INIT, INSTR_CNOT, INSTR_H, \
    INSTR_MEASURE
from netsquid.components.qprogram import QuantumProgram
from netsquid.qubits.ketstates import BellIndex
from qlink_interface import (
    ReqCreateAndKeep,
    ReqReceive,
    ResCreateAndKeep,
)

from netsquid_netbuilder.protocol_base import BlueprintProtocol
from pydynaa import EventExpression


def bell_state_corrections(egp_result: ResCreateAndKeep, qdevice: QuantumProcessor):
    qubit_mem_pos = egp_result.logical_qubit_id
    bell_state = egp_result.bell_state
    if bell_state == BellIndex.B00:
        pass
    elif egp_result.bell_state == BellIndex.B01:
        prog = QuantumProgram()
        prog.apply(INSTR_ROT_X, qubit_indices=[qubit_mem_pos], angle=math.pi)
        yield qdevice.execute_program(prog)
    elif bell_state == BellIndex.B10:
        prog = QuantumProgram()
        prog.apply(INSTR_ROT_Z, qubit_indices=[qubit_mem_pos], angle=math.pi)
        yield qdevice.execute_program(prog)
    elif bell_state == BellIndex.B11:
        prog = QuantumProgram()
        prog.apply(INSTR_ROT_X, qubit_indices=[qubit_mem_pos], angle=math.pi)
        prog.apply(INSTR_ROT_Z, qubit_indices=[qubit_mem_pos], angle=math.pi)
        yield qdevice.execute_program(prog)


def prepare_qubit(qdevice: QuantumProcessor, phi: float = 0, theta: float = 0):
    if len(qdevice.unused_positions) == 0:
        raise RuntimeError("No free memory positions")
    qubit_position = qdevice.unused_positions[0]
    qdevice.mem_positions[qubit_position].in_use = True
    prog = QuantumProgram()
    prog.apply(INSTR_INIT, qubit_indices=[qubit_position])
    if theta != 0:
        prog.apply(INSTR_ROT_Y, qubit_indices=[qubit_position], angle=theta)
    if phi != 0:
        prog.apply(INSTR_ROT_Z, qubit_indices=[qubit_position], angle=phi)
    yield qdevice.execute_program(prog)

    return qubit_position


def teleport_send(qdevice: QuantumProcessor, teleportation_qubit_mem_pos: int, epr_qubit_mem_pos) -> Generator[EventExpression, None, Tuple[int, int]]:
    prog = QuantumProgram()
    prog.apply(INSTR_CNOT, qubit_indices=[teleportation_qubit_mem_pos, epr_qubit_mem_pos])
    prog.apply(INSTR_H, qubit_indices=[teleportation_qubit_mem_pos])
    prog.apply(INSTR_MEASURE, qubit_indices=[teleportation_qubit_mem_pos], output_key="m1")
    prog.apply(INSTR_MEASURE, qubit_indices=[epr_qubit_mem_pos], output_key="m2")

    yield qdevice.execute_program(prog)
    return prog.output["m1"][0], prog.output["m2"][0]


def teleport_receive(qdevice: QuantumProcessor, epr_qubit_mem_pos: int, m1: int, m2: int) -> Generator[EventExpression, None, None]:
    prog = QuantumProgram()
    if m2 == 1:
        prog.apply(INSTR_ROT_X, qubit_indices=[epr_qubit_mem_pos], angle=math.pi)
    if m1 == 1:
        prog.apply(INSTR_ROT_Z, qubit_indices=[epr_qubit_mem_pos], angle=math.pi)

    yield qdevice.execute_program(prog)


class TeleportationSenderProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        qdevice: QuantumProcessor = self.context.node.qdevice
        socket = self.context.sockets[self.PEER]
        egp = self.context.egp[self.PEER]

        request = ReqCreateAndKeep(remote_node_id=self.context.node_id_mapping[self.PEER])
        egp.put(request)

        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        egp_result = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        print(f"{ns.sim_time()} ns: Alice completes entanglement generation")

        teleport_qubit_mem_pos = yield from prepare_qubit(qdevice, theta=math.pi, phi=0)

        qubit: Qubit = qdevice.peek(positions=teleport_qubit_mem_pos)[0]
        dm = netsquid.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
        print(f"{ns.sim_time()} ns: Alice prepared the teleportation qubit:\n{dm}")

        m1, m2 = yield from teleport_send(qdevice, teleport_qubit_mem_pos, egp_result.logical_qubit_id)
        print(f"{ns.sim_time()} ns: Alice teleports the qubit with m1={m1} m2={m2}")
        socket.send(str(m1))
        socket.send(str(m2))


class TeleportationReceiverProtocol(BlueprintProtocol):
    def __init__(self, peer_name: str):
        super().__init__()
        self.PEER = peer_name

    def run(self) -> Generator[EventExpression, None, None]:
        qdevice: QuantumProcessor = self.context.node.qdevice
        socket = self.context.sockets[self.PEER]
        egp = self.context.egp[self.PEER]

        egp.put(ReqReceive(remote_node_id=self.context.node_id_mapping[self.PEER]))

        yield self.await_signal(sender=egp, signal_label=ResCreateAndKeep.__name__)
        response = egp.get_signal_result(label=ResCreateAndKeep.__name__, receiver=self)
        qubit: Qubit = qdevice.peek(positions=response.logical_qubit_id)[0]
        dm = netsquid.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
        print(f"{ns.sim_time()} ns: Bob completes entanglement generation with bell state {response.bell_state}:\n{dm}")

        yield from bell_state_corrections(response, qdevice)
        dm = netsquid.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
        print(f"{ns.sim_time()} ns: Bob performed the bell state corrections:\n{dm}")

        m1 = yield from socket.recv()
        m2 = yield from socket.recv()

        m1 = int(m1)
        m2 = int(m2)
        print(f"{ns.sim_time()} ns: Bob receives m1={m1} m2={m2}")

        yield from teleport_receive(qdevice, response.logical_qubit_id, m1, m2)

        dm = netsquid.qubits.qubitapi.reduced_dm(qubit.qstate.qubits)
        print(f"{ns.sim_time()} ns: Bob finished teleportation routine:\n{dm}")

