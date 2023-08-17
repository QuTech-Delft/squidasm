from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from netsquid.components import Port
    from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
    from netsquid_netbuilder.builder.metro_hub import MetroHub
    from netsquid_netbuilder.builder.network_builder import ProtocolController
    from netsquid_netbuilder.builder.repeater_chain import Chain

    from squidasm.sim.stack.egp import EgpProtocol
    from squidasm.sim.stack.stack import ProcessingNode


class ProtocolContext:
    def __init__(
        self,
        node: ProcessingNode,
        links: Dict[str, MagicLinkLayerProtocolWithSignaling],
        egp: Dict[str, EgpProtocol],
        node_id_mapping: Dict[str, int],
        ports: Dict[str, Port],
    ):
        self.node = node
        self.links = links
        self.egp = egp
        self.node_id_mapping = node_id_mapping
        self.ports = ports


class Network:
    def __init__(self):
        self.end_nodes: Dict[str, ProcessingNode] = {}
        self.links: Dict[(str, str), MagicLinkLayerProtocolWithSignaling] = {}
        self.hubs: Dict[str, MetroHub] = {}
        self.chains: Dict[(str, str), Chain] = {}
        self.egp: Dict[(str, str), EgpProtocol] = {}
        self.ports: Dict[(str, str), Port] = {}
        self.node_name_id_mapping: Dict[str, int] = {}
        self._protocol_controller: Optional[ProtocolController] = None

    def get_protocol_context(self, node_name: str) -> ProtocolContext:
        node = self.end_nodes[node_name]
        links = self.filter_for_id(node_name, self.links)
        egp = self.filter_for_id(node_name, self.egp)
        ports = self.filter_for_id(node_name, self.ports)

        return ProtocolContext(node, links, egp, self.node_name_id_mapping, ports)

    class Role(Enum):
        END_NODE = auto()
        REPEATER = auto()
        HUB = auto()

    def find_role(self, node_name: str) -> Role:
        if node_name in self.end_nodes:
            return self.Role.END_NODE
        # Merge all repeaters node names into a single list using sum(.., [])
        elif node_name in sum(
            [list(chain.repeater_nodes_dict.keys()) for chain in self.chains.values()],
            [],
        ):
            return self.Role.REPEATER
        elif node_name in [hub.hub_node.name for hub in self.hubs.values()]:
            return self.Role.HUB
        else:
            raise ValueError(f"Could not find node: {node_name} in network")

    @staticmethod
    def filter_for_id(
        node_id: str, dictionary: Dict[(str, str), any]
    ) -> Dict[str, any]:
        keys = dictionary.keys()
        keys = filter(lambda key_tuple: key_tuple[0] == node_id, keys)
        return {key[1]: dictionary[key] for key in keys}

    def start(self):
        self._protocol_controller.start_all()

    def stop(self):
        self._protocol_controller.stop_all()
