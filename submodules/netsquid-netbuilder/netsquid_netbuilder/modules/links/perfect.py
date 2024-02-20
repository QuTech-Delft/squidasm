from __future__ import annotations

import copy
from typing import Optional

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import SingleClickTranslationUnit
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor
from netsquid_netbuilder.modules.links.interface import ILinkConfig, ILinkBuilder
from netsquid_netbuilder.nodes import QDeviceNode


class PerfectLinkConfig(ILinkConfig):
    state_delay: Optional[float] = None
    """Time to complete entanglement generation. [ns]"""
    length: Optional[float] = None
    """length of the link. Will be used to calculate state_delay with state_delay=length/speed_of_light. [km]"""
    speed_of_light: float = 200000
    """Speed of light in th optical fiber connecting the two nodes. [km/s]"""

    def set_default(self):
        self.state_delay = 1000.0


class PerfectLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: QDeviceNode, node2: QDeviceNode,
              link_cfg: PerfectLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        link_cfg = cls._pre_process_config(link_cfg)

        link_dist = PerfectStateMagicDistributor(
            nodes=[node1, node2],
            state_delay=link_cfg.state_delay,
            label_delay=0.,
            cycle_time=link_cfg.state_delay,
        )
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot

    @classmethod
    def _pre_process_config(cls, link_cfg: PerfectLinkConfig) -> PerfectLinkConfig:
        if isinstance(link_cfg, dict):
            link_cfg = PerfectLinkConfig(**link_cfg)
        else:
            link_cfg = copy.deepcopy(link_cfg)

        if link_cfg.state_delay is None and link_cfg.length is None:
            link_cfg.set_default()
        if link_cfg.state_delay is not None and link_cfg.length is not None:
            raise ValueError(f"{cls.__name__} model config can only use t_cycle or distance, but both where specified")
        if link_cfg.length is not None:
            link_cfg.state_delay = link_cfg.length / link_cfg.speed_of_light * 1e9
        return link_cfg
