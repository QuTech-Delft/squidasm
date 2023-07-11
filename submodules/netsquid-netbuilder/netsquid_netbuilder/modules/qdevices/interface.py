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
