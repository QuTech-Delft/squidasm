from __future__ import annotations

import copy
from typing import Optional

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import SingleClickTranslationUnit
from netsquid_magic.magic_distributor import DepolariseWithFailureMagicDistributor
from netsquid_netbuilder.modules.links.interface import ILinkConfig, ILinkBuilder
from netsquid_netbuilder.util.fidelity import fidelity_to_prob_max_mixed
from netsquid_netbuilder.nodes import QDeviceNode


class DepolariseLinkConfig(ILinkConfig):
    """Simple model for a link to generate EPR pairs."""

    fidelity: float
    """Fidelity of successfully generated EPR pairs."""
    prob_success: float
    """Probability of successfully generating an EPR per cycle."""
    t_cycle: Optional[float]
    """Duration of a cycle. [ns]"""
    length: Optional[float]
    """length of the link. Will be used to calculate t_cycle with t_cycle=length/speed_of_light. [km]"""
    speed_of_light: float = 200000
    """Speed of light in th optical fiber connecting the two nodes. [km/s]"""


class DepolariseLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: QDeviceNode, node2: QDeviceNode, link_cfg: DepolariseLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        link_cfg = cls._pre_process_config(link_cfg)

        prob_max_mixed = fidelity_to_prob_max_mixed(link_cfg.fidelity)
        link_dist = DepolariseWithFailureMagicDistributor(
            nodes=[node1, node2],
            prob_max_mixed=prob_max_mixed,
            prob_success=link_cfg.prob_success,
            cycle_time=link_cfg.t_cycle,
            label_delay=0.,
            state_delay=link_cfg.t_cycle,
        )

        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot

    @classmethod
    def _pre_process_config(cls, link_cfg: DepolariseLinkConfig) -> DepolariseLinkConfig:
        if isinstance(link_cfg, dict):
            link_cfg = DepolariseLinkConfig(**link_cfg)
        else:
            link_cfg = copy.deepcopy(link_cfg)
        if link_cfg.t_cycle is None and (link_cfg.length is None or link_cfg.speed_of_light is None):
            raise ValueError(f"{cls.__name__} model config requires a t_cycle"
                             f" or distance with speed of light specification")
        if link_cfg.t_cycle is not None and link_cfg.length is not None:
            raise ValueError(f"{cls.__name__} model config can only use t_cycle or distance, but both where specified")
        if link_cfg.length is not None:
            link_cfg.t_cycle = link_cfg.length / link_cfg.speed_of_light * 1e9
        return link_cfg


