from __future__ import annotations

from typing import Dict

from netsquid.components import Port
from netsquid.nodes import Node
from netsquid.nodes.connections import DirectConnection


def create_connection_ports(n1: Node, n2: Node, connection: DirectConnection, port_prefix: str)\
        -> Dict[(str, str), Port]:
    out = {}

    n1_port: Port = n1.add_ports([f"{port_prefix}_{n2.ID}"])[0]
    n2_port: Port = n2.add_ports([f"{port_prefix}_{n1.ID}"])[0]

    # link
    n1_port.connect(connection.port_A)
    n2_port.connect(connection.port_B)

    out[(n1.name, n2.name)] = n2_port
    out[(n2.name, n1.name)] = n1_port

    return out
