from __future__ import annotations

from typing import Dict, List

from netsquid.components import QuantumProcessor
from netsquid.nodes.network import Network
from netsquid_magic.link_layer import MagicLinkLayerProtocol

from squidasm.qoala.sim.procnode import ProcNode


class ProcNodeNetwork(Network):
    """A network of `ProcNode`s connected by links, which are
    `MagicLinkLayerProtocol`s."""

    def __init__(
        self, nodes: Dict[str, ProcNode], links: List[MagicLinkLayerProtocol]
    ) -> None:
        """ProcNodeNetwork constructor.

        :param nodes: dictionary of node name to `ProcNode` object representing
        that node
        :param links: list of link layer protocol objects. Each object internally
        contains the IDs of the two nodes that this link connects
        """
        self._nodes = nodes
        self._links = links

    @property
    def nodes(self) -> Dict[str, ProcNode]:
        return self._nodes

    @property
    def links(self) -> List[MagicLinkLayerProtocol]:
        return self._links

    @property
    def qdevices(self) -> Dict[str, QuantumProcessor]:
        return {name: node.qdevice for name, node in self._nodes.items()}
