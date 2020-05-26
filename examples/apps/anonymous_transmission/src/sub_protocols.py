from netqasm.sdk.toolbox import create_ghz


def classical_anonymous_transmission(
    conn,
    sockets,
    num_nodes,
    sender=False,
    value=None,
):
    if sender:
        assert isinstance(value, bool), f"Value should be boolen, not {type(value)}"

    # Create a GHZ state
    q, _ = create_ghz(
        down_epr_socket=sockets.down_epr_socket,
        up_epr_socket=sockets.up_epr_socket,
        down_socket=sockets.down_socket,
        up_socket=sockets.up_socket,
        do_corrections=True,
    )

    # If sender and value is 1/True do Z flip
    if sender and value:
        q.Z()

    # Hadamard and measure
    q.H()
    m = q.measure()

    # Flush the commands to get the outcome
    conn.flush()

    # Send outcome to all other nodes
    broadcast_channel = sockets.broadcast_channel
    broadcast_channel.send(str(m))

    # Get measurements from all other nodes
    k = m
    for _ in range(num_nodes - 1):
        remote_node, m = broadcast_channel.recv()
        k += int(m)

    message = k % 2 == 1

    return message
