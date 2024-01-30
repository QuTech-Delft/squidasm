from abc import ABC, abstractmethod

from netsquid.components import QuantumProcessor
from netsquid_netbuilder.yaml_loadable import YamlLoadable


class IQDeviceConfig(YamlLoadable, ABC):
    pass


class IQDeviceBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(cls, name: str, qdevice_cfg: IQDeviceConfig) -> QuantumProcessor:
        pass

    @classmethod
    def build_services(cls, node):
        pass
        # TODO make abstract, possibly rework this entire system, as this is just draft
