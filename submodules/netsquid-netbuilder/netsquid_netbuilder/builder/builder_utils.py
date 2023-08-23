from __future__ import annotations

from typing import Dict

from netsquid.components import Port
from netsquid.nodes import Node
from netsquid.nodes.connections import DirectConnection
from netsquid_netbuilder.modules.links.interface import ILinkConfig


def create_connection_ports(
    n1: Node, n2: Node, connection: DirectConnection, port_prefix: str
) -> Dict[(str, str), Port]:
    out = {}

    n1_port: Port = n1.add_ports([f"Port_{port_prefix}_({n1.name},{n2.name})"])[0]
    n2_port: Port = n2.add_ports([f"Port_{port_prefix}_({n2.name},{n1.name})"])[0]

    # link
    n1_port.connect(connection.port_A)
    n2_port.connect(connection.port_B)

    out[(n1.name, n2.name)] = n1_port
    out[(n2.name, n1.name)] = n2_port

    return out


def link_has_length(config: ILinkConfig):
    if hasattr(config, "length"):
        return True
    if hasattr(
        config,
        "length_A",
    ) and hasattr(config, "length_B"):
        return True
    return False


def link_set_length(config: ILinkConfig, dist1: float, dist2: float):
    if hasattr(
        config,
        "length_A",
    ) and hasattr(config, "length_B"):
        config.length_A = dist1
        config.length_B = dist2
        return

    if hasattr(config, "length"):
        config.length = dist1 + dist2
