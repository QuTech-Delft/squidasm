from __future__ import annotations
from blueprint.yaml_loadable import YamlLoadable


class HeraldedLinkConfig(YamlLoadable):
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
