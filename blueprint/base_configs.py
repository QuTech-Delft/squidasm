from __future__ import annotations
from typing import Any, List

from blueprint.yaml_loadable import YamlLoadable


class LinkConfig(YamlLoadable):
    """Configuration for a single link."""

    stack1: str
    """Name of the first stack being connected via link."""
    stack2: str
    """Name of the second stack being connected via link."""
    typ: str
    """Type of the link."""
    cfg: Any
    """Configuration of the link, allowed configuration depends on type."""

    @classmethod
    def perfect_config(cls, stack1: str, stack2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(stack1=stack1, stack2=stack2, typ="perfect", cfg=None)


class CLinkConfig(YamlLoadable):
    """Configuration for a single clink."""

    stack1: str
    """Name of the first stack being connected via clink."""
    stack2: str
    """Name of the second stack being connected via clink."""
    typ: str
    """Type of the clink."""
    cfg: Any
    """Configuration of the clink, allowed configuration depends on type."""

    @classmethod
    def perfect_config(cls, stack1: str, stack2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(stack1=stack1, stack2=stack2, typ="instant", cfg=None)


class StackConfig(YamlLoadable):
    """Configuration for a single stack (i.e. end node)."""

    name: str
    """Name of the stack."""
    qdevice_typ: str
    """Type of the quantum device."""
    qdevice_cfg: Any
    """Configuration of the quantum device, allowed configuration depends on type."""


class StackNetworkConfig(YamlLoadable):
    """Full network configuration."""

    stacks: List[StackConfig]
    """List of all the stacks in the network."""
    links: List[LinkConfig]
    """List of all the links connecting the stacks in the network."""
    clinks: List[CLinkConfig]
    """List of all the clinks connecting the stacks in the network."""
