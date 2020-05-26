from collections import namedtuple

from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from netqasm.sdk import ThreadBroadcastChannel as BroadcastChannel


Sockets = namedtuple("Sockets", [
    "broadcast_channel",
    "down_epr_socket",
    "down_socket",
    "up_epr_socket",
    "up_socket",
    "epr_sockets",
])


def setup_sockets(node_name, nodes, log_subroutines_dir):
    broadcast_channel = _setup_broadcast_channel(node_name, nodes, log_subroutines_dir)
    down_epr_socket, down_socket = _setup_down_sockets(node_name, nodes, log_subroutines_dir)
    up_epr_socket, up_socket = _setup_up_sockets(node_name, nodes, log_subroutines_dir)
    epr_sockets = [epr_socket for epr_socket in [down_epr_socket, up_epr_socket] if epr_socket is not None]

    return Sockets(
        broadcast_channel=broadcast_channel,
        down_epr_socket=down_epr_socket,
        down_socket=down_socket,
        up_epr_socket=up_epr_socket,
        up_socket=up_socket,
        epr_sockets=epr_sockets,
    )


def _setup_broadcast_channel(node_name, node_names, log_subroutines_dir):
    # Create a broadcast_channel to send classical information
    remote_node_names = [nn for nn in node_names if nn != node_name]
    broadcast_channel = BroadcastChannel(
        node_name,
        remote_node_names=remote_node_names,
        comm_log_dir=log_subroutines_dir,
        socket_id=1,
    )

    return broadcast_channel


def _setup_down_sockets(node_name, node_names, log_subroutines_dir):
    index = node_names.index(node_name)
    if index > 0:
        down_node = node_names[index - 1]
    else:
        down_node = None
    return _setup_sockets(node_name, down_node, log_subroutines_dir)


def _setup_up_sockets(node_name, node_names, log_subroutines_dir):
    index = node_names.index(node_name)
    if index < len(node_names) - 1:
        up_node = node_names[index + 1]
    else:
        up_node = None
    return _setup_sockets(node_name, up_node, log_subroutines_dir)


def _setup_sockets(node_name, other_node, log_subroutines_dir):
    if other_node is None:
        return None, None
    epr_socket = EPRSocket(other_node)
    socket = Socket(node_name, other_node, comm_log_dir=log_subroutines_dir)
    return epr_socket, socket
