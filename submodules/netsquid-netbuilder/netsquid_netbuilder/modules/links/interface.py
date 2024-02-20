from abc import ABC, abstractmethod

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.yaml_loadable import YamlLoadable

from netsquid_netbuilder.nodes import QDeviceNode


class ILinkConfig(YamlLoadable, ABC):
    pass


class ILinkBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(
        cls, node1: QDeviceNode, node2: QDeviceNode, link_cfg: ILinkConfig
    ) -> MagicLinkLayerProtocolWithSignaling:
        pass
