from __future__ import annotations

import itertools
from typing import Any, List, Optional

import netsquid_netbuilder.modules.clinks as netbuilder_clinks
import netsquid_netbuilder.modules.qdevices as netbuilder_qdevices
import netsquid_netbuilder.modules.qlinks as netbuilder_links
import netsquid_netbuilder.network_config as netbuilder_configs
from netsquid_netbuilder.yaml_loadable import YamlLoadable


class GenericQDeviceConfig(netbuilder_qdevices.GenericQDeviceConfig):
    __doc__ = netbuilder_qdevices.GenericQDeviceConfig.__doc__


class NVQDeviceConfig(netbuilder_qdevices.NVQDeviceConfig):
    __doc__ = netbuilder_qdevices.NVQDeviceConfig.__doc__


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
            qdevice_cfg=netbuilder_qdevices.GenericQDeviceConfig.perfect_config(),
        )


class DepolariseLinkConfig(netbuilder_links.DepolariseQLinkConfig):
    __doc__ = netbuilder_links.DepolariseQLinkConfig.__doc__


class HeraldedLinkConfig(netbuilder_links.HeraldedDoubleClickQLinkConfig):
    __doc__ = netbuilder_links.HeraldedDoubleClickQLinkConfig.__doc__


class InstantCLinkConfig(netbuilder_clinks.InstantCLinkConfig):
    __doc__ = netbuilder_clinks.InstantCLinkConfig.__doc__


class DefaultCLinkConfig(netbuilder_clinks.DefaultCLinkConfig):
    __doc__ = netbuilder_clinks.DefaultCLinkConfig.__doc__


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


class StackNetworkConfig(YamlLoadable):
    """Full network configuration."""

    stacks: List[StackConfig]
    """List of all the stacks in the network."""
    links: List[LinkConfig]
    """List of all the links connecting the stacks in the network."""
    clinks: Optional[List[CLinkConfig]]
    """List of all the links connecting the stacks in the network."""

    @classmethod
    def from_file(cls, path: str) -> StackNetworkConfig:
        return super().from_file(path)  # type: ignore


def _convert_stack_network_config(
    stack_network_config: StackNetworkConfig,
) -> netbuilder_configs.NetworkConfig:

    # Convert stack nodes to processing nodes
    processing_nodes = []
    for stack_config in stack_network_config.stacks:
        processing_node = netbuilder_configs.ProcessingNodeConfig(
            name=stack_config.name,
            qdevice_typ=stack_config.qdevice_typ,
            qdevice_cfg=stack_config.qdevice_cfg,
        )
        processing_nodes.append(processing_node)

    # Convert link config types
    qlinks = []
    for link_config in stack_network_config.links:
        link_typ = link_config.typ
        link_cfg = link_config.cfg
        if link_typ == "heralded":
            link_typ = "heralded-double-click"
        if link_cfg is None and link_typ == "perfect":
            link_cfg = netbuilder_links.PerfectQLinkConfig()

        link = netbuilder_configs.QLinkConfig(
            node1=link_config.stack1,
            node2=link_config.stack2,
            typ=link_typ,
            cfg=link_cfg,
        )
        qlinks.append(link)

    # If clinks are given convert types, if not connect all nodes
    clinks = []
    if stack_network_config.clinks:
        for clink_config in stack_network_config.clinks:
            clink = netbuilder_configs.CLinkConfig(
                node1=clink_config.stack1,
                node2=clink_config.stack2,
                typ=clink_config.typ,
                cfg=clink_config.cfg,
            )
            clinks.append(clink)
    else:
        # Link all nodes with instant classical connections
        for node1, node2 in itertools.combinations(processing_nodes, 2):
            clink = netbuilder_configs.CLinkConfig(
                node1=node1.name,
                node2=node2.name,
                typ="instant",
                cfg=netbuilder_clinks.InstantCLinkConfig(),
            )
            clinks.append(clink)

    return netbuilder_configs.NetworkConfig(
        processing_nodes=processing_nodes, qlinks=qlinks, clinks=clinks
    )
