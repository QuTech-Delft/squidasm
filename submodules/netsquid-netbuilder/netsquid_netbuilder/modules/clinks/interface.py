from abc import ABC, abstractmethod

from netsquid.nodes.connections import DirectConnection
from netsquid_netbuilder.yaml_loadable import YamlLoadable

from netsquid.nodes import Node


class ICLinkConfig(YamlLoadable, ABC):
    pass


class ICLinkBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(
        cls, node1: Node, node2: Node, link_cfg: ICLinkConfig
    ) -> DirectConnection:
        pass
