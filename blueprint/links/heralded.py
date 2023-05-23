from __future__ import annotations

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import (
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    DoubleClickMagicDistributor,
)
from netsquid_physlayer.heralded_connection import MiddleHeraldedConnection

from blueprint.links.interface import ILinkConfig, ILinkBuilder
from squidasm.sim.stack.stack import ProcessingNode


class HeraldedLinkConfig(ILinkConfig):
    """The heralded link uses a model with both nodes connected by fiber to a midpoint station with a
    Bell-state measurement detector.
    The nodes repeatedly send out entangled photons and, on a successful measurement at the midpoint,
    the midpoint station will send out a signal to both nodes, heralding successful entanglement.
    The heralded link uses the double click model as developed and described by:
    https://arxiv.org/abs/2207.10579"""

    length: float
    """Total length of the heralded connection in km. (i.e. sum of fibers on both sides on midpoint station)"""
    p_loss_init: float = 0
    """Probability that photons are lost when entering connection the connection on either side."""
    p_loss_length: float = 0.25
    """Attenuation coefficient [dB/km] of fiber on either side."""
    speed_of_light: float = 200_000
    """Speed of light [km/s] in fiber on either side."""
    dark_count_probability: float = 0
    """dark-count probability per detection."""
    detector_efficiency: float = 1.0
    """Probability that the presence of a photon leads to a detection event."""
    visibility: float = 1.0
    """Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)"""
    num_resolving: bool = False
    """Determines whether photon-number-resolving detectors are used for the Bell-state measurement."""


class HeraldedLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode,
              link_cfg: HeraldedLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        if isinstance(link_cfg, dict):
            link_cfg = HeraldedLinkConfig(**link_cfg)

        connection = MiddleHeraldedConnection(
            name="heralded_conn", **link_cfg.dict()
        )
        link_dist = DoubleClickMagicDistributor(
            [node1, node2], connection
        )
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot
