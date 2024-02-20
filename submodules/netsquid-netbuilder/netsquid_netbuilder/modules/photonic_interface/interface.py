from __future__ import annotations
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

from netsquid_netbuilder.yaml_loadable import YamlLoadable
if TYPE_CHECKING:
    from netsquid_magic.photonic_interface import IPhotonicInterface


class IPhotonicInterfaceConfig(YamlLoadable, ABC):
    pass


class IPhotonicInterfaceBuilder(ABC):
    @classmethod
    @abstractmethod
    def build(
        cls, photonic_interface_cfg: IPhotonicInterfaceConfig
    ) -> IPhotonicInterface:
        pass
