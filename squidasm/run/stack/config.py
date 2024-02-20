from __future__ import annotations

import itertools
from typing import Any, List

from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig
from netsquid_netbuilder.yaml_loadable import YamlLoadable


class StackConfig(YamlLoadable):
    """Configuration for a single stack (i.e. end node)."""

    name: str
    """Name of the stack."""
    qdevice_typ: str
    """Type of the quantum device."""
    qdevice_cfg: Any = None
    """Configuration of the quantum device, allowed configuration depends on type."""

    @classmethod
    def from_file(cls, path: str) -> StackConfig:
        return cls._from_file(path)  # type: ignore

    @classmethod
    def perfect_generic_config(cls, name: str) -> StackConfig:
        """Create a configuration for a stack with a generic quantum device without any noise or errors."""
        return StackConfig(
            name=name,
            qdevice_typ="generic",
            qdevice_cfg=GenericQDeviceConfig.perfect_config(),
        )


class LinkConfig(YamlLoadable):
    """Configuration for a single link."""

    stack1: str
    """Name of the first stack being connected via link."""
    stack2: str
    """Name of the second stack being connected via link."""
    typ: str
    """Type of the link."""
    cfg: Any = None
    """Configuration of the link, allowed configuration depends on type."""

    @classmethod
    def from_file(cls, path: str) -> LinkConfig:
        return cls._from_file(path)  # type: ignore

    @classmethod
    def perfect_config(cls, stack1: str, stack2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(stack1=stack1, stack2=stack2, typ="perfect", cfg=None)


class StackNetworkConfig(YamlLoadable):
    """Full network configuration."""

    stacks: List[StackConfig]
    """List of all the stacks in the network."""
    links: List[LinkConfig]
    """List of all the links connecting the stacks in the network."""

    @classmethod
    def from_file(cls, path: str) -> StackNetworkConfig:
        return cls._from_file(path)  # type: ignore


def _convert_stack_network_config(
    stack_network_config: StackNetworkConfig,
) -> NetworkConfig:
    # Convert stack nodes to processing nodes
    processing_nodes = []
    for stack_config in stack_network_config.stacks:
        pass

    for link_config in stack_network_config.links:
        pass

    # Link all nodes with instant classical connections
    for node1, node2 in itertools.combinations(processing_nodes, 2):
        pass

    return NetworkConfig()
