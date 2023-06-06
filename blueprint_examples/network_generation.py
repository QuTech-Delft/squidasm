import itertools

from blueprint.base_configs import StackNetworkConfig, StackConfig, LinkConfig
from blueprint.links.interface import ILinkConfig


def create_2_node_network(link_typ: str, link_cfg: ILinkConfig) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[])

    node_names = ["Alice", "Bob"]
    for node_name in node_names:
        stack = StackConfig(name=node_name,
                            qdevice_typ="generic",
                            qdevice_cfg={})
        network_config.stacks.append(stack)

    link = LinkConfig(stack1=node_names[0],
                      stack2=node_names[1],
                      typ=link_typ,
                      cfg=link_cfg)
    network_config.links.append(link)

    return network_config


def create_multi_node_network(num_nodes: int, link_typ: str, link_cfg: ILinkConfig) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[])

    node_names = [f"node_{i}" for i in range(num_nodes)]
    for node_name in node_names:
        stack = StackConfig(name=node_name,
                            qdevice_typ="generic",
                            qdevice_cfg={})
        network_config.stacks.append(stack)

    for s1, s2 in itertools.combinations(node_names, 2):
        link = LinkConfig(stack1=s1,
                          stack2=s2,
                          typ=link_typ,
                          cfg=link_cfg)
        network_config.links.append(link)

    return network_config
