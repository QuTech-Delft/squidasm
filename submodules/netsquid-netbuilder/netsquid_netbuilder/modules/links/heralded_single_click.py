from __future__ import annotations

import copy
from typing import Optional

from netsquid_netbuilder.modules.links.util import set_heralded_side_length, set_heralded_side_parameters
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.link_layer import SingleClickTranslationUnit
from netsquid_magic.magic_distributor import SingleClickMagicDistributor
from netsquid_netbuilder.modules.links.interface import ILinkConfig, ILinkBuilder
from netsquid_netbuilder.nodes import QDeviceNode


class HeraldedSingleClickLinkConfig(ILinkConfig):
    """The heralded link uses a model with both nodes connected by fiber to a midpoint station with a
    Bell-state measurement detector.
    The nodes repeatedly send out entangled photons and, on a successful measurement at the midpoint,
    the midpoint station will send out a signal to both nodes, heralding successful entanglement.

    The parameters length, p_loss_init, p_loss_length, speed_of_light and emission_fidelity can be specified
     per side of the heralded link. These parameters have a "global" parameter and per side parameters with _A and _B
     extensions. The model will use the per side parameters,
      but for easier usage, the input can be set to the "global" parameter that will
      be distributed to each of the sides if their value is missing.

    Note
    ----
    Currently only works when the entanglement generation is completely symmetric between sides "A" and "B".

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

    length_A: Optional[float] = None
    """length [km] of fiber on "A" side of heralded connection"""
    p_loss_init_A: Optional[float] = None
    p_loss_length_A: Optional[float] = None
    speed_of_light_A: Optional[float] = None
    emission_fidelity_A: Optional[float] = None
    """length [km] of fiber on "B" side of heralded connection"""
    length_B: Optional[float] = None
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


class HeraldedSingleClickLinkBuilder(ILinkBuilder):
    @classmethod
    def build(cls, node1: QDeviceNode, node2: QDeviceNode,
              link_cfg: HeraldedSingleClickLinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        link_cfg = cls._pre_process_config(link_cfg)

        link_dist = SingleClickMagicDistributor([node1, node2], None, **link_cfg.dict())
        link_prot = MagicLinkLayerProtocolWithSignaling(
            nodes=[node1, node2],
            magic_distributor=link_dist,
            translation_unit=SingleClickTranslationUnit(),
        )
        return link_prot

    @classmethod
    def _pre_process_config(cls, link_cfg: HeraldedSingleClickLinkConfig) -> HeraldedSingleClickLinkConfig:
        if isinstance(link_cfg, dict):
            link_cfg = HeraldedSingleClickLinkConfig(**link_cfg)
        else:
            link_cfg = copy.deepcopy(link_cfg)

        defaults_dict = HeraldedSingleClickLinkConfig.get_defaults()
        set_heralded_side_length(link_cfg)
        set_heralded_side_parameters(link_cfg, "p_loss_init", defaults_dict)
        set_heralded_side_parameters(link_cfg, "p_loss_length", defaults_dict)
        set_heralded_side_parameters(link_cfg, "speed_of_light", defaults_dict)
        set_heralded_side_parameters(link_cfg, "emission_fidelity", defaults_dict)

        return link_cfg
