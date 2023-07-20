"""Utility functions for examples"""
from typing import Generator, List

import netsquid.qubits
import numpy as np
from netqasm.sdk.qubit import Qubit
from netsquid.qubits import operators
from netsquid.qubits import qubitapi as qapi

import squidasm.sim.stack.globals
from squidasm.run.stack.config import (
    DepolariseLinkConfig,
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.sim.stack.program import ProgramContext


def measXY(q, angle: float):
    """Measure qubit `q` in the basis spanned by `|0> ± e^{i*angle} |1>`.
    This is equivalent to doing a Z-rotation of `angle`, then a Hadamard,
    and measuring in the Z-basis.
    Note: we use the convention that we rotate by +`angle` (not -`angle`).
    """
    q.rot_Z(angle=angle)
    q.H()
    return q.measure()


def remote_state_preparation(epr_socket, theta: float):
    """Prepare a state Rz(theta)|+> to the server.
    The resulting state on the server's side is actually
    Rz(theta + m*pi) |+>, for the client's measurement outcome `m`.
    """
    epr = epr_socket.create_keep()[0]
    m = measXY(epr, theta)
    return m


def recv_remote_state_preparation(epr_socket):
    """Let the client prepare a state on the server.
    The client will do a suitable measurement on her side.
    """
    return epr_socket.recv_keep()[0]


def send_float(socket, phi):
    """Send a float"""
    socket.send(str(phi))


def recv_float(socket) -> Generator[None, None, float]:
    """Receive a float"""
    val = yield from socket.recv()
    assert isinstance(val, str)
    return float(val)


def send_int(socket, outcome: int):
    """Send a integer"""
    socket.send(str(outcome))


def recv_int(socket) -> Generator[None, None, int]:
    """Receive a float"""
    val = yield from socket.recv()
    assert isinstance(val, str)
    return int(val)


def teleport_send(
    q: Qubit, context: ProgramContext, peer_name: str
) -> Generator[None, None, None]:
    """
    Sending segment of a teleportation protocol. =
    This is a generator and requires use of `yield from` in usage order to function.
    :param q: Qubit to teleport. This qubit will be measured and 'destroyed'.
    :param context: context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    # Create EPR pairs
    epr = epr_socket.create_keep()[0]

    # Teleport
    q.cnot(epr)
    q.H()
    m1 = q.measure()
    m2 = epr.measure()
    yield from connection.flush()

    # Send the correction information
    m1, m2 = int(m1), int(m2)
    csocket.send(f"{m1},{m2}")


def teleport_recv(
    context: ProgramContext, peer_name: str
) -> Generator[None, None, Qubit]:
    """
    Receiving segment of a teleportation protocol. Will return the teleported qubit.
    This is a generator and requires use of `yield from` in usage order to function.

    :param context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    :return: Teleported qubit
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    # Generate EPR pair
    epr = epr_socket.recv_keep()[0]
    yield from connection.flush()

    # Receive corrections
    msg = yield from csocket.recv()
    assert isinstance(msg, str)
    m1, m2 = msg.split(",")
    # Apply corrections
    if int(m2) == 1:
        epr.X()
    if int(m1) == 1:
        epr.Z()

    yield from connection.flush()

    return epr


def distributed_CNOT_control(
    context: ProgramContext, peer_name: str, ctrl_qubit: Qubit
) -> Generator[None, None, None]:
    """
    Performs the two qubit CNOT gate, but with the control qubit located on this node, the target on a remote node.
    This is a generator and requires use of `yield from` in usage order to function.

    :param context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    :param ctrl_qubit: The control qubit. Will not be affected in an ideal scenario.
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    epr = epr_socket.create_keep()[0]
    ctrl_qubit.cnot(epr)
    epr_meas = epr.measure()
    yield from connection.flush()

    csocket.send(str(epr_meas))
    target_meas = yield from csocket.recv()
    if target_meas == "1":
        ctrl_qubit.Z()

    yield from connection.flush()


def distributed_CNOT_target(
    context: ProgramContext, peer_name: str, target_qubit: Qubit
):
    """
    Performs the two qubit CNOT gate, but with the target qubit located on this node, the control on a remote node.
    This is a generator and requires use of `yield from` in usage order to function.

    :param context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    :param target_qubit: The target qubit. Will be operated on depending on the control qubit state.
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    epr = epr_socket.recv_keep()[0]
    yield from connection.flush()

    m = yield from csocket.recv()
    if m == "1":
        epr.X()

    epr.cnot(target_qubit)

    epr.H()
    epr_meas = epr.measure()
    yield from connection.flush()

    csocket.send(str(epr_meas))


def distributed_CPhase_control(
    context: ProgramContext, peer_name: str, ctrl_qubit: Qubit
) -> Generator[None, None, None]:
    """
    Performs the two qubit Cphase gate, but with the control qubit located on this node, the target on a remote node.
    This is a generator and requires use of `yield from` in usage order to function.

    :param context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    :param ctrl_qubit: The control qubit. Will not be affected in an ideal scenario.
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    epr = epr_socket.create_keep()[0]
    ctrl_qubit.cnot(epr)
    epr_meas = epr.measure()
    yield from connection.flush()

    csocket.send(str(epr_meas))
    target_meas = yield from csocket.recv()
    if target_meas == "1":
        ctrl_qubit.Z()

    yield from connection.flush()


def distributed_CPhase_target(
    context: ProgramContext, peer_name: str, target_qubit: Qubit
):
    """
    Performs the two qubit CNOT gate, but with the target qubit located on this node, the control on a remote node.
    This is a generator and requires use of `yield from` in usage order to function.

    :param context: context of the current program
    :param peer_name: name of the peer engaging in this teleportation protocol
    :param target_qubit: The target qubit. Will be operated on depending on the control qubit state.
    """
    csocket = context.csockets[peer_name]
    epr_socket = context.epr_sockets[peer_name]
    connection = context.connection

    epr = epr_socket.recv_keep()[0]
    yield from connection.flush()

    m = yield from csocket.recv()
    if m == "1":
        epr.X()

    epr.cphase(target_qubit)
    epr.H()
    epr_meas = epr.measure()
    yield from connection.flush()

    csocket.send(str(epr_meas))


def create_two_node_network(
    node_names: List[str] = None, link_noise: float = 0, qdevice_noise: float = 0
) -> StackNetworkConfig:
    """
    Create a network configuration with two nodes, with simple noise models.
    :param node_names: List of str with the names of the two nodes
    :param link_noise: A number between 0 and 1 that indicates how noisy the generated EPR pairs are.
    :param qdevice_noise: A number between 0 and 1 that indicates how noisy the qubit operations on the nodes are.
    :return: StackNetworkConfig object with a two node network
    """
    node_names = ["Alice", "Bob"] if node_names is None else node_names
    assert len(node_names) == 2

    qdevice_cfg = GenericQDeviceConfig.perfect_config()
    qdevice_cfg.two_qubit_gate_depolar_prob = qdevice_noise
    qdevice_cfg.single_qubit_gate_depolar_prob = qdevice_noise
    qdevice_cfg.num_qubits = 10
    stacks = [
        StackConfig(name=name, qdevice_typ="generic", qdevice_cfg=qdevice_cfg)
        for name in node_names
    ]

    link_cfg = DepolariseLinkConfig(
        fidelity=1 - link_noise * 3 / 4, t_cycle=1000, prob_success=1
    )
    link = LinkConfig(
        stack1=node_names[0], stack2=node_names[1], typ="depolarise", cfg=link_cfg
    )
    return StackNetworkConfig(stacks=stacks, links=[link])


def get_qubit_state(q: Qubit, node_name, full_state=False) -> np.ndarray:
    """
    Retrieves the underlying quantum state from a qubit in density matrix formalism.
     This is only possible in simulation.

    .. note:: The function gets the *current* qubit. So make sure the subroutine is flushed
              before calling the method.

    :param q: The qubit to get the state of or list of qubits.
    :param node_name:  Node name of current node.
    Requirement for this parameter is due to software limitation,
     can be made unnecessary in future version of SquidASM.
    :param full_state: Flag to retrieve the full underlying entangled state and not only this qubit subspace.
    :return: An array that is the density matrix description of the quantum state
    """
    # Get the executor and qmemory from the backend
    network = squidasm.sim.stack.globals.GlobalSimData.get_network()
    app_id = q._conn.app_id

    executor = network.stacks[node_name].qnos.app_memories[app_id]
    qmemory = network.stacks[node_name].qdevice

    # Get the physical position of the qubit
    virtual_address = q.qubit_id
    phys_pos = executor.phys_id_for(virt_id=virtual_address)

    # Get the netsquid qubit
    ns_qubit = qmemory.mem_positions[phys_pos].get_qubit()

    if full_state:
        ns_qubit = ns_qubit.qstate.qubits

    dm = qapi.reduced_dm(ns_qubit)

    return dm


def get_reference_state(phi: float, theta: float) -> np.ndarray:
    """
    Gives the reference quantum state for a qubit in density matrix formalism,
     that is in a pure state matching a state on the Bloch sphere described by the angles phi and theta.

    :param phi: Angle on Bloch sphere between state and x-axis
    :param theta: Angle on Bloch sphere between state and z-axis
    :return: An array that is the density matrix description of the quantum state
    """
    q = netsquid.qubits.create_qubits(1)[0]
    rot_y = operators.create_rotation_op(theta, (0, 1, 0))
    rot_z = operators.create_rotation_op(phi, (0, 0, 1))
    netsquid.qubits.operate(q, rot_y)
    netsquid.qubits.operate(q, rot_z)
    return qapi.reduced_dm(q)
