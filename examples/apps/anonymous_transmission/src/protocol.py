from netqasm.logging import get_netqasm_logger
from squidasm.sdk import NetSquidConnection

from .sub_protocols import classical_anonymous_transmission
from .setup import setup_sockets
from .conf import nodes

logger = get_netqasm_logger()


def anonymous_transmission(
    node_name,
    sender=False,
    value=None,
    log_subroutines_dir=None,
    track_lines=True,
):

    # Setup sockets, epr_sockets and a broadcast_channel needed for the protocol
    sockets = setup_sockets(
        node_name=node_name,
        nodes=nodes,
        log_subroutines_dir=log_subroutines_dir,
    )

    # Initialize the connection to the backend
    conn = NetSquidConnection(
        name=node_name,
        track_lines=True,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=sockets.epr_sockets,
    )
    with conn:
        msg = classical_anonymous_transmission(
            conn=conn,
            sockets=sockets,
            num_nodes=len(nodes),
            sender=sender,
            value=value,
        )
    logger.info(f'{node_name}: msg = {msg}')
    return {'msg': msg}
