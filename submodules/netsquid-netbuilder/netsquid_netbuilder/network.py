from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, Optional, List
from dataclasses import dataclass, field

from netsquid_netbuilder.modules.scheduler.interface import IScheduleProtocol

if TYPE_CHECKING:
    from netsquid.components import Port
    from netsquid.nodes.node import Node
    from netsquid_driver.classical_socket_service import ClassicalSocket
    from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
    from netsquid_netbuilder.builder.metro_hub import MetroHub
    from netsquid_netbuilder.builder.network_builder import ProtocolController
    from netsquid_netbuilder.builder.repeater_chain import Chain

    from squidasm.sim.stack.egp import EGPService
    from netsquid_netbuilder.nodes import MetroHubNode, ProcessingNode, RepeaterNode, NodeWithDriver


class ProtocolContext:
    def __init__(
        self,
        node: Node,
        links: Dict[str, MagicLinkLayerProtocolWithSignaling],
        egp: Dict[str, EGPService],
        node_id_mapping: Dict[str, int],
        sockets: Dict[str, ClassicalSocket],
        ports: Dict[str, Port],
    ):
        self.node = node
        self.links = links
        self.egp = egp
        self.node_id_mapping = node_id_mapping
        self.sockets = sockets
        self.ports = ports


class Network:
    def __init__(self):
        self.end_nodes: Dict[str, ProcessingNode] = {}
        self.links: Dict[(str, str), MagicLinkLayerProtocolWithSignaling] = {}
        self.hubs: Dict[str, MetroHub] = {}
        self.chains: Dict[(str, str), Chain] = {}
        self.sockets: Dict[(str, str), ClassicalSocket] = {}
        self.egp: Dict[(str, str), EGPService] = {}
        self.ports: Dict[(str, str), Port] = {}
        self.node_name_id_mapping: Dict[str, int] = {}
        self._protocol_controller: Optional[ProtocolController] = None

    def get_protocol_context(self, node_name: str) -> ProtocolContext:
        node = self.end_nodes[node_name]
        links = self.filter_for_node(node_name, self.links)
        egp = self.filter_for_node(node_name, self.egp)
        ports = self.filter_for_node(node_name, self.ports)
        sockets = self.filter_for_node(node_name, self.sockets)

        return ProtocolContext(
            node, links, egp, self.node_name_id_mapping, sockets, ports
        )

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

    @property
    def nodes(self) -> Dict[str, NodeWithDriver]:
        nodes = {}
        nodes.update(self.end_nodes)
        nodes.update({hub_name: hub.hub_node for hub_name, hub in self.hubs.items()})
        for chain in self.chains.values():
            nodes.update(chain.repeater_nodes_dict)

        return nodes

    @staticmethod
    def filter_for_node(
        node_name: str, dictionary: Dict[(str, str), any]
    ) -> Dict[str, any]:
        keys = dictionary.keys()
        keys = filter(lambda key_tuple: key_tuple[0] == node_name, keys)
        return {key[1]: dictionary[key] for key in keys}

    def start(self):
        self._protocol_controller.start_all()

    def stop(self):
        self._protocol_controller.stop_all()


@dataclass
class MetroHub:
    hub_node: MetroHubNode = None
    end_nodes: Dict[str, ProcessingNode] = field(default_factory=dict)
    scheduler: IScheduleProtocol = None
    end_node_lengths: Dict[str, float] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.hub_node.name


@dataclass
class Chain:
    hub_1: MetroHub
    hub_2: MetroHub
    repeater_nodes: List[RepeaterNode] = field(default_factory=list)
    link_lengths: List[float] = field(default_factory=list)
    scheduler = None

    @property
    def name(self) -> str:
        return f"Chain ({self.hub_1.name}-{self.hub_2.name})"

    @property
    def repeater_nodes_dict(self) -> Dict[str, RepeaterNode]:
        return {node.name: node for node in self.repeater_nodes}
