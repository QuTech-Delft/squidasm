from abc import ABC, abstractmethod

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.yaml_loadable import YamlLoadable
from squidasm.sim.stack.stack import ProcessingNode


class ILinkConfig(YamlLoadable, ABC):
    pass


class ILinkBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode, link_cfg: ILinkConfig) -> MagicLinkLayerProtocolWithSignaling:
        pass


