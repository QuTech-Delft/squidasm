from __future__ import annotations

import copy
from typing import Optional

from netsquid_netbuilder.modules.links.util import set_heralded_side_length, set_heralded_side_parameters
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import SingleClickTranslationUnit
from netsquid_magic.magic_distributor import DoubleClickMagicDistributor
from netsquid_netbuilder.modules.links.interface import ILinkConfig, ILinkBuilder
from netsquid_netbuilder.nodes import QDeviceNode


class HeraldedDoubleClickLinkConfig(ILinkConfig):
    """The heralded link uses a model with both nodes connected by fiber to a midpoint station with a
    Bell-state measurement detector.
    The nodes repeatedly send out entangled photons and, on a successful measurement at the midpoint,
    the midpoint station will send out a signal to both nodes, heralding successful entanglement.
    The heralded link uses the double click model as developed and described by:
    https://arxiv.org/abs/2207.10579

    The parameters length, p_loss_init, p_loss_length, speed_of_light and emission_fidelity can be specified
     per side of the heralded link. These parameters have a "global" parameter and per side parameters with _A and _B
     extensions. The model will use the per side parameters,
      but for easier usage, the input can be set to the "global" parameter that will
      be distributed to each of the sides if their value is missing.
    """

    length: Optional[float] = None
    """Total length [km] of fiber. "A" and "B" side are assumed to be equally long"""
    p_loss_init: Optional[float] = None
    """probability that photons are lost when entering connection"""
    p_loss_length: Optional[float] = None
    """attenuation coefficient [dB/km] of the fiber"""
    speed_of_light: Optional[float] = None
    """speed of light [km/s] in fiber of the heralded connection"""
    emission_fidelity: Optional[float] = None
    """Fidelity of state shared between photon and memory qubit to
    :meth:`~netsquid.qubits.ketstates.BellIndex.PHI_PLUS` Bell state directly after emission."""
    dark_count_probability: float = 0
    """dark-count probability per detection"""
    detector_efficiency: float = 1
    """probability that the presence of a photon leads to a detection event"""
    visibility: float = 1
    """Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)"""
    num_resolving: bool = False
    """determines whether photon-number-resolving detectors are used for the Bell-state measurement"""
    coin_prob_ph_ph: float = 1
    """Coincidence probability for two photons. When using a coincidence time window in the double-click protocol,
    two clicks are only accepted if they occurred within one coincidence time window away from each other.
    This parameter is the probability that if both clicks are photon detections,
    they are within one coincidence window. In general, this depends not only on the size of the coincidence
    time window, but also on the state of emitted photons and the total detection time window. Defaults to 1."""
    coin_prob_ph_dc: float = 1
    """Coincidence probability for a photon and a dark count.
    When using a coincidence time window in the double-click protocol,
    two clicks are only accepted if they occurred within one coincidence time window away from each other.
    This parameter is the probability that if one click is a photon detection and the other a dark count,
    they are within one coincidence window. In general, this depends not only on the size of the coincidence
    time window, but also on the state of emitted photons and the total detection time window. Defaults to 1."""
    coin_prob_dc_dc: float = 1
    """Coincidence probability for two dark counts. When using a coincidence time window in the double-click protocol,
    two clicks are only accepted if they occurred within one coincidence time window away from each other.
    This parameter is the probability that if both clicks are dark counts,
    they are within one coincidence window. In general, this depends on the size of the coincidence time window
    and the total detection time window. Defaults to 1."""
    num_multiplexing_modes: int = 1
    """Number of modes used for multiplexing, i.e. how often entanglement generation is attempted per round."""

    length_A: Optional[float] = None
    """length [km] of fiber on "A" side of heralded connection"""
    p_loss_init_A: Optional[float] = None
    p_loss_length_A: Optional[float] = None
    speed_of_light_A: Optional[float] = None
    emission_fidelity_A: Optional[float] = None
    length_B: Optional[float] = None
    """length [km] of fiber on "B" side of heralded connection"""
    p_loss_init_B: Optional[float] = None
    p_loss_length_B: Optional[float] = None
    speed_of_light_B: Optional[float] = None
    emission_fidelity_B: Optional[float] = None

    @staticmethod
    def get_defaults():
        return {
            "p_loss_init": 0,
            "p_loss_length": 0.25,
            "speed_of_light": 200000,
            "emission_fidelity": 1,
        }


class HeraldedDoubleClickLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: QDeviceNode, node2: QDeviceNode,
              link_cfg: HeraldedDoubleClickLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        if isinstance(link_cfg, dict):
            link_cfg = HeraldedDoubleClickLinkConfig(**link_cfg)
        link_cfg = cls._pre_process_config(link_cfg)

        link_dist = DoubleClickMagicDistributor([node1, node2], None, **link_cfg.dict())
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot

    @classmethod
    def _pre_process_config(cls, link_cfg: HeraldedDoubleClickLinkConfig) -> HeraldedDoubleClickLinkConfig:
        if isinstance(link_cfg, dict):
            link_cfg = HeraldedDoubleClickLinkConfig(**link_cfg)
        else:
            link_cfg = copy.deepcopy(link_cfg)

        defaults_dict = HeraldedDoubleClickLinkConfig.get_defaults()
        set_heralded_side_length(link_cfg)
        set_heralded_side_parameters(link_cfg, "p_loss_init", defaults_dict)
        set_heralded_side_parameters(link_cfg, "p_loss_length", defaults_dict)
        set_heralded_side_parameters(link_cfg, "speed_of_light", defaults_dict)
        set_heralded_side_parameters(link_cfg, "emission_fidelity", defaults_dict)

        return link_cfg
