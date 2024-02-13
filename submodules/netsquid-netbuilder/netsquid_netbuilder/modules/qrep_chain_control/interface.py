from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, TYPE_CHECKING

from netsquid_driver.EGP import EGPService
from netsquid_netbuilder.network import Network
from netsquid_netbuilder.yaml_loadable import YamlLoadable
if TYPE_CHECKING:
    from netsquid_netbuilder.builder.repeater_chain import Chain


class IQRepChainControlConfig(YamlLoadable, ABC):
    pass


class IQRepChainControlBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(
            cls, chain: Chain, network: Network, control_cfg: IQRepChainControlConfig) -> Dict[(str, str), EGPService]:
        pass
