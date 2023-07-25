from typing import Generator

from netqasm.sdk.qubit import Qubit

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
    Sending routine of a teleportation protocol.
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
    Receiving routine of a teleportation protocol. Will return the teleported qubit.
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
    The formal return is a generator and requires use of `yield from` in usage in order to function as intended.

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
