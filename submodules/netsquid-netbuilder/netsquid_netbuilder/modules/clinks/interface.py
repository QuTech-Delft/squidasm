from abc import ABC, abstractmethod

from netsquid.nodes.connections import DirectConnection

from netsquid_netbuilder.yaml_loadable import YamlLoadable
from squidasm.sim.stack.stack import ProcessingNode


class ICLinkConfig(YamlLoadable, ABC):
    pass


class ICLinkBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode, link_cfg: ICLinkConfig) -> DirectConnection:
        pass
