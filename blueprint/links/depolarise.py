from __future__ import annotations
from blueprint.yaml_loadable import YamlLoadable


class DepolariseLinkConfig(YamlLoadable):
    """Simple model for a link to generate EPR pairs."""

    fidelity: float
    """Fidelity of successfully generated EPR pairs."""
    prob_success: float
    """Probability of successfully generating an EPR per cycle."""
    t_cycle: float
    """Duration of a cycle in nano seconds."""

