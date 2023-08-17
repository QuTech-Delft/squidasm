import itertools
from typing import List, Union

from netsquid_netbuilder.base_configs import (
    CLinkConfig,
    LinkConfig,
    MetroHubConfig,
    MetroHubConnectionConfig,
    RepeaterChainConfig,
    StackConfig,
    StackNetworkConfig,
)
from netsquid_netbuilder.modules.clinks.instant import InstantCLinkConfig
from netsquid_netbuilder.modules.clinks.interface import ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceConfig
from netsquid_netbuilder.modules.scheduler.fifo import FIFOScheduleConfig
from netsquid_netbuilder.modules.scheduler.interface import IScheduleConfig


def create_single_node_network(qdevice_typ: str, qdevice_cfg: IQDeviceConfig):
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

    stack = StackConfig(name="Alice", qdevice_typ=qdevice_typ, qdevice_cfg=qdevice_cfg)
    network_config.stacks.append(stack)

    return network_config


def create_2_node_network(
    link_typ: str,
    link_cfg: ILinkConfig,
    clink_typ: str = "instant",
    clink_cfg: ICLinkConfig = None,
    qdevice_typ: str = "generic",
    qdevice_cfg: IQDeviceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

    node_names = ["Alice", "Bob"]
    for node_name in node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(
            name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg=qdevice_cfg
        )
        network_config.stacks.append(stack)

    link = LinkConfig(
        stack1=node_names[0], stack2=node_names[1], typ=link_typ, cfg=link_cfg
    )
    network_config.links.append(link)

    clink = CLinkConfig(
        stack1=node_names[0], stack2=node_names[1], typ=clink_typ, cfg=clink_cfg
    )
    network_config.clinks.append(clink)

    return network_config


def create_multi_node_network(
    num_nodes: int,
    link_typ: str,
    link_cfg: ILinkConfig,
    clink_typ: str = "instant",
    clink_cfg: ICLinkConfig = None,
    qdevice_typ: str = "generic",
    qdevice_cfg: IQDeviceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

    node_names = [f"node_{i}" for i in range(num_nodes)]
    for node_name in node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg={})
        network_config.stacks.append(stack)

    for s1, s2 in itertools.combinations(node_names, 2):
        link = LinkConfig(stack1=s1, stack2=s2, typ=link_typ, cfg=link_cfg)
        network_config.links.append(link)

        clink = CLinkConfig(stack1=s1, stack2=s2, typ=clink_typ, cfg=clink_cfg)
        network_config.clinks.append(clink)

    return network_config


def create_metro_hub_network(
    num_nodes: int,
    node_distances: Union[float, List[float]],
    link_typ: str,
    link_cfg: ILinkConfig,
    schedule_typ: str = "fifo",
    schedule_cfg: IScheduleConfig = None,
    clink_typ: str = "instant",
    clink_cfg: ICLinkConfig = None,
    qdevice_typ: str = "generic",
    qdevice_cfg: IQDeviceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])
    clink_cfg = InstantCLinkConfig() if clink_cfg is None else clink_cfg

    node_names = [f"node_{i}" for i in range(num_nodes)]
    for node_name in node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg={})
        network_config.stacks.append(stack)

    mh_connections = connect_mh(num_nodes, node_distances, node_names)

    schedule_cfg = FIFOScheduleConfig() if schedule_cfg is None else schedule_cfg

    mh = MetroHubConfig(
        name="metro hub",
        connections=mh_connections,
        link_typ=link_typ,
        link_cfg=link_cfg,
        clink_typ=clink_typ,
        clink_cfg=clink_cfg,
        schedule_typ=schedule_typ,
        schedule_cfg=schedule_cfg,
    )
    network_config.hubs = [mh]

    return network_config


def connect_mh(
    num_nodes: int, node_distances: Union[float, List[float]], node_names: List[str]
) -> List[MetroHubConnectionConfig]:
    mh_connections = []
    node_distances = (
        [node_distances for _ in range(num_nodes)]
        if not isinstance(node_distances, list)
        else node_distances
    )
    for node_name, dist in zip(node_names, node_distances):
        mh_connections.append(MetroHubConnectionConfig(stack=node_name, length=dist))

    return mh_connections


def create_qia_prototype_network(
    num_nodes_hub1: int,
    node_distances_hub1: Union[float, List[float]],
    num_nodes_hub2: int,
    node_distances_hub2: Union[float, List[float]],
    num_nodes_repeater_chain: int,
    node_distances_repeater_chain: Union[float, List[float]],
    link_typ: str,
    link_cfg: ILinkConfig,
    schedule_typ: str = "fifo",
    schedule_cfg: IScheduleConfig = None,
    clink_typ: str = "instant",
    clink_cfg: ICLinkConfig = None,
    qdevice_typ: str = "generic",
    qdevice_cfg: IQDeviceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])
    clink_cfg = InstantCLinkConfig() if clink_cfg is None else clink_cfg

    hub1_node_names = [f"hub1_node_{i}" for i in range(num_nodes_hub1)]
    hub2_node_names = [f"hub2_node_{i}" for i in range(num_nodes_hub2)]

    for node_name in hub1_node_names + hub2_node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg={})
        network_config.stacks.append(stack)

    mh1_connections = connect_mh(num_nodes_hub1, node_distances_hub1, hub1_node_names)
    mh2_connections = connect_mh(num_nodes_hub2, node_distances_hub2, hub2_node_names)

    schedule_cfg = FIFOScheduleConfig() if schedule_cfg is None else schedule_cfg

    mh1 = MetroHubConfig(
        name="mh1",
        connections=mh1_connections,
        link_typ=link_typ,
        link_cfg=link_cfg,
        clink_typ=clink_typ,
        clink_cfg=clink_cfg,
        schedule_typ=schedule_typ,
        schedule_cfg=schedule_cfg,
    )
    mh2 = MetroHubConfig(
        name="mh2",
        connections=mh2_connections,
        link_typ=link_typ,
        link_cfg=link_cfg,
        clink_typ=clink_typ,
        clink_cfg=clink_cfg,
        schedule_typ=schedule_typ,
        schedule_cfg=schedule_cfg,
    )
    network_config.hubs = [mh1, mh2]

    repeater_node_names = [
        f"repeater_node_{i}" for i in range(num_nodes_repeater_chain)
    ]
    repeater_stacks = []
    for node_name in repeater_node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg={})
        repeater_stacks.append(stack)

    node_distances_repeater_chain = (
        node_distances_repeater_chain
        if isinstance(node_distances_repeater_chain, list)
        else [
            node_distances_repeater_chain for _ in range(num_nodes_repeater_chain + 1)
        ]
    )

    repeater_chain = RepeaterChainConfig(
        metro_hub1="mh1",
        metro_hub2="mh2",
        link_typ=link_typ,
        link_cfg=link_cfg,
        clink_typ=clink_typ,
        clink_cfg=clink_cfg,
        repeater_nodes=repeater_stacks,
        lengths=node_distances_repeater_chain,
        schedule_typ="TODO",
        schedule_cfg=None,
    )
    network_config.repeater_chains = [repeater_chain]

    return network_config
