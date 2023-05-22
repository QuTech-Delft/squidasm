from __future__ import annotations
from blueprint.yaml_loadable import YamlLoadable


class NVLinkConfig(YamlLoadable):
    length_A: float
    length_B: float
    full_cycle: float
    cycle_time: float
    alpha: float

