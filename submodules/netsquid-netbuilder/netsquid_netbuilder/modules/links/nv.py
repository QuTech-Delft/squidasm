from __future__ import annotations

from netsquid_magic.link_layer import (
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_nv.magic_distributor import NVSingleClickMagicDistributor

from netsquid_netbuilder.nodes import QDeviceNode


class NVLinkConfig(ILinkConfig):
    length_A: float
    length_B: float
    full_cycle: float
    cycle_time: float
    alpha: float


class NVLinkBuilder(ILinkBuilder):
    @classmethod
    def build(
        cls, node1: QDeviceNode, node2: QDeviceNode, link_cfg: NVLinkConfig
    ) -> MagicLinkLayerProtocolWithSignaling:
        if isinstance(link_cfg, dict):
            link_cfg = NVLinkConfig(**link_cfg)

        link_dist = NVSingleClickMagicDistributor(
            nodes=[node1, node2],
            length_A=link_cfg.length_A,
            length_B=link_cfg.length_B,
            full_cycle=link_cfg.full_cycle,
            cycle_time=link_cfg.cycle_time,
            alpha=link_cfg.alpha,
        )
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot
