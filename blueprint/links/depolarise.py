from __future__ import annotations

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import (
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    DepolariseWithFailureMagicDistributor,
)

from blueprint.links.interface import ILinkConfig, ILinkBuilder
from squidasm.sim.stack.stack import ProcessingNode


class DepolariseLinkConfig(ILinkConfig):
    """Simple model for a link to generate EPR pairs."""

    fidelity: float
    """Fidelity of successfully generated EPR pairs."""
    prob_success: float
    """Probability of successfully generating an EPR per cycle."""
    t_cycle: float
    """Duration of a cycle in nano seconds."""


class DepolariseLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode, link_cfg: ILinkConfig) -> MagicLinkLayerProtocolWithSignaling:

        if isinstance(link_cfg, dict):
            link_cfg = DepolariseLinkConfig(**link_cfg)
        prob_max_mixed = fidelity_to_prob_max_mixed(link_cfg.fidelity)
        link_dist = DepolariseWithFailureMagicDistributor(
            nodes=[node1, node2],
            prob_max_mixed=prob_max_mixed,
            prob_success=link_cfg.prob_success,
            t_cycle=link_cfg.t_cycle,
        )

        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0
