from enum import Enum, auto
from typing import Generator, Optional, Tuple

from netqasm.sdk import EPRSocket
from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
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
    """Prepare a state :math:`R_z(theta)|+>` to the server.
    The resulting state on the server's side is actually
    :math:`R_z(theta + m*\\pi) |+>`, for the client's measurement outcome `m`.
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


class _Role(Enum):
    start = auto()
    middle = auto()
    end = auto()


def create_ghz(
    connection: BaseNetQASMConnection,
    down_epr_socket: Optional[EPRSocket] = None,
    up_epr_socket: Optional[EPRSocket] = None,
    down_socket: Optional[Socket] = None,
    up_socket: Optional[Socket] = None,
    do_corrections: bool = False,
) -> Generator[None, None, Tuple[Qubit, int]]:
    r"""Local protocol to create a GHZ state between multiples nodes.

    EPR pairs are generated in a line and turned into a GHZ state by performing half of a Bell measurement.
    That is, CNOT and H are applied but only the control qubit is measured.
    If `do_corrections=False` (default) this measurement outcome is returned along with the qubit to be able to know
    what corrections might need to be applied.
    If the node is at the start or end of the line, the measurement outcome 0 is always returned since there
    is no measurement performed.
    The measurement outcome indicates if the next node in the line should flip its qubit to get the standard
    GHZ state: :math:`|0\rangle^{\otimes n} + |1\rangle^{\otimes n}`.

    On the other hand if `do_corrections=True`, then the classical sockets `down_socket` and/or `up_socket`
    will be used to communicate the outcomes and automatically perform the corrections.

    Depending on if down_epr_socket and/or up_epr_socket is specified the node,
    either takes the role of the:

    * "start", which initialises the process and creates an EPR
      with the next node using the `up_epr_socket`.
    * "middle", which receives an EPR pair on the `down_epr_socket` and then
      creates one on the `up_epr_socket`.
    * "end", which receives an EPR pair on the `down_epr_socket`.

    .. note::
        There has to be exactly one "start" and exactly one "end" but zero or more "middle".
        Both `down_epr_socket` and `up_epr_socket` cannot be `None`.

    :param connection: The connection to the quantum node controller used for sending instructions.
    :param down_epr_socket: The EPRSocket to be used for receiving EPR pairs from downstream.
    :param up_epr_socket: The EPRSocket to be used for create EPR pairs upstream.
    :param down_socket: The classical socket to be used for sending corrections, if `do_corrections = True`.
    :param up_socket: The classical socket to be used for sending corrections, if `do_corrections = True`.
    :param do_corrections: If corrections should be applied to make the GHZ in the standard form
        :math:`|0\rangle^{\otimes n} + |1\rangle^{\otimes n}` or not.
    :return: Of the form `(q, m)` where `q` is the qubit part of the state and `m` is the measurement outcome.
    """
    if down_epr_socket is None and up_epr_socket is None:
        raise TypeError("Both down_epr_socket and up_epr_socket cannot be None")

    if down_epr_socket is None:
        # Start role
        role = _Role.start
        yield from up_socket.recv()
        q = up_epr_socket.create_keep()[0]
        m = 0
    else:
        down_socket.send("")
        q = down_epr_socket.recv_keep()[0]
        if up_epr_socket is None:
            # End role
            role = _Role.end
            m = 0
        else:
            # Middle role
            role = _Role.middle

            yield from up_socket.recv()

            q_up: Qubit = up_epr_socket.create_keep()[0]  # type: ignore
            # merge the states by doing half a Bell measurement
            q.cnot(q_up)
            m = q_up.measure()

    # Flush the subroutine
    yield from connection.flush()

    if do_corrections:
        if role == _Role.start:
            assert up_socket is not None
            up_socket.send(str(0))
        else:
            assert down_socket is not None
            corr = yield from down_socket.recv()
            assert isinstance(corr, str)
            corr = int(corr)
            if corr == 1:
                q.X()
            if role == _Role.middle:
                assert up_socket is not None
                corr = (corr + m) % 2
                up_socket.send(str(corr))
        yield from connection.flush()
        m = 0

    return q, int(m)
