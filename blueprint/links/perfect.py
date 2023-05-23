from __future__ import annotations

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import (
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    PerfectStateMagicDistributor,
)

from blueprint.links.interface import ILinkConfig, ILinkBuilder
from squidasm.sim.stack.stack import ProcessingNode


class PerfectLinkConfig(ILinkConfig):
    state_delay: float = 1000.


class PerfectLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode,
              link_cfg: PerfectLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        if isinstance(link_cfg, dict):
            link_cfg = PerfectLinkConfig(**link_cfg)

        link_dist = PerfectStateMagicDistributor(
            nodes=[node1, node2], state_delay=link_cfg.state_delay
        )
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot
