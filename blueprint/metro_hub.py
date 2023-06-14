from __future__ import annotations

from typing import Dict, List, Optional
from squidasm.sim.stack.csocket import ClassicalSocket

from netsquid.components import QuantumProcessor
from netsquid.components.component import Port
from netsquid.nodes import Node
from netsquid.nodes.network import Network
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
)
from squidasm.sim.stack.egp import EgpProtocol


class MetroHubNode(Node):
    def __init__(
        self,
        name: str,
        node_id: Optional[int] = None,
    ) -> None:

        super().__init__(name, ID=node_id)

