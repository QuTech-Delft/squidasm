from __future__ import annotations

from typing import Any, List, Optional

from netsquid_netbuilder.yaml_loadable import YamlLoadable


class LinkConfig(YamlLoadable):
    """Configuration for a single quantum link that enables nodes to generate EPR pairs between them."""

    node1: str
    """Name of the first node being connected via link."""
    node2: str
    """Name of the second node being connected via link."""
    typ: str
    """Type of the link."""
    cfg: Any
    """Configuration of the link, allowed configuration depends on type."""

    @classmethod
    def perfect_config(cls, node1: str, node2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(node1=node1, node2=node2, typ="perfect", cfg=None)


class CLinkConfig(YamlLoadable):
    """Configuration for a single classical link."""

    node1: str
    """Name of the first node being connected via clink."""
    node2: str
    """Name of the second node being connected via clink."""
    typ: str
    """Type of the clink."""
    cfg: Any
    """Configuration of the clink, allowed configuration depends on type."""

    @classmethod
    def perfect_config(cls, node1: str, node2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(node1=node1, node2=node2, typ="instant", cfg=None)


class ProcessingNodeConfig(YamlLoadable):
    """Configuration for a single processing node."""

    name: str
    """Name of the node."""
    qdevice_typ: str
    """Type of the quantum device."""
    qdevice_cfg: Any
    """Configuration of the quantum device, allowed configuration depends on type."""


class RepeaterNodeConfig(ProcessingNodeConfig):
    """Configuration for a repeater node."""


class MetroHubConnectionConfig(YamlLoadable):
    node: str
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

    repeater_nodes: List[RepeaterNodeConfig]
    lengths: List[float]

    photonic_interface_typ: Optional[str]
    photonic_interface_loc: str = "end"
    photonic_interface_cfg: Optional[Any]

    qrep_chain_control_typ: str
    qrep_chain_control_cfg: Any


class NetworkConfig(YamlLoadable):
    """Full network configuration."""

    processing_nodes: List[ProcessingNodeConfig]
    """List of all the processing nodes in the network."""
    links: Optional[List[LinkConfig]]
    """List of all the links connecting the nodes in the network."""
    clinks: Optional[List[CLinkConfig]]
    """List of all the clinks connecting the nodes in the network."""

    hubs: Optional[List[MetroHubConfig]]
    """List of all the metro hubs in the network"""
    repeater_chains: Optional[List[RepeaterChainConfig]]
    """List of all the repeater chains in the network"""
