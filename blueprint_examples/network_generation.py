import itertools

from blueprint.base_configs import StackNetworkConfig, StackConfig, LinkConfig, CLinkConfig
from blueprint.links.interface import ILinkConfig
from blueprint.clinks.interface import ICLinkConfig


def create_2_node_network(link_typ: str, link_cfg: ILinkConfig,
                          clink_typ: str = "instant", clink_cfg: ICLinkConfig = None) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

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

    clink = CLinkConfig(stack1=node_names[0],
                        stack2=node_names[1],
                        typ=clink_typ,
                        cfg=clink_cfg)
    network_config.clinks.append(clink)

    return network_config


def create_multi_node_network(num_nodes: int, link_typ: str, link_cfg: ILinkConfig,
                              clink_typ: str = "instant", clink_cfg: ICLinkConfig = None
                              ) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

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

        clink = CLinkConfig(stack1=s1,
                            stack2=s2,
                            typ=clink_typ,
                            cfg=clink_cfg)
        network_config.clinks.append(clink)



    return network_config
