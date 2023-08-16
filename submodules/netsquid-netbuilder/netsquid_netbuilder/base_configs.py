from __future__ import annotations

from typing import Any, List, Optional

from netsquid_netbuilder.yaml_loadable import YamlLoadable


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


class MetroHubConnectionConfig(YamlLoadable):
    stack: str
    length: float


class MetroHubConfig(YamlLoadable):
    name: str
    """Name of the hub"""
    connections: List[MetroHubConnectionConfig]
    """Names of the connected hubs"""
    link_typ: str
    link_cfg: Any

    clink_typ: str
    clink_cfg: Any

    schedule_typ: str
    schedule_cfg: Any


class RepeaterChainConfig(YamlLoadable):
    metro_hub1: str
    metro_hub2: str

    link_typ: str
    link_cfg: Any

    clink_typ: str
    clink_cfg: Any

    repeater_nodes: List[StackConfig]
    lengths: List[float]

    schedule_typ: str
    schedule_cfg: Any


# class DriverConfig(YamlLoadable):
#     preset: Optional[str]
#     """Preset to use"""
#     services: Optional[List[ServiceConfig]]
#     """Additional services to use install"""
#
#
# class ServiceConfig(YamlLoadable):
#     name: str


class StackNetworkConfig(YamlLoadable):
    """Full network configuration."""

    stacks: List[StackConfig]
    """List of all the stacks in the network."""
    links: Optional[List[LinkConfig]]
    """List of all the links connecting the stacks in the network."""
    clinks: Optional[List[CLinkConfig]]
    """List of all the clinks connecting the stacks in the network."""
    hubs: Optional[List[MetroHubConfig]]
    """List of all the metro hubs in the network"""
    repeater_chains: Optional[List[RepeaterChainConfig]]
    """List of all the repeater chains in the network"""
