import itertools
from typing import List, Union

from netsquid_magic.models.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.base_configs import (
    CLinkConfig,
    LinkConfig,
    MetroHubConfig,
    MetroHubConnectionConfig,
    StackConfig,
    StackNetworkConfig,
)
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
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
    node_names = ["Alice", "Bob"]
    return create_complete_graph_network(
        node_names, link_typ, link_cfg, clink_typ, clink_cfg, qdevice_typ, qdevice_cfg
    )


def create_complete_graph_network(
    node_names: List[str],
    link_typ: str,
    link_cfg: ILinkConfig,
    clink_typ: str = "instant",
    clink_cfg: ICLinkConfig = None,
    qdevice_typ: str = "generic",
    qdevice_cfg: IQDeviceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

    assert len(node_names) > 0

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

    for s1, s2 in itertools.combinations(node_names, 2):
        link = LinkConfig(stack1=s1, stack2=s2, typ=link_typ, cfg=link_cfg)
        network_config.links.append(link)

        clink = CLinkConfig(stack1=s1, stack2=s2, typ=clink_typ, cfg=clink_cfg)
        network_config.clinks.append(clink)

    return network_config


def create_simple_network(
    node_names: List[str],
    link_noise: float = 0,
    qdevice_noise: float = 0,
    qdevice_depolar_time: float = 0,
    qdevice_op_time: float = 0,
    clink_delay: float = 0.0,
    link_delay: float = 0.0,
) -> StackNetworkConfig:
    """
    Create a complete graph network configuration with simple noise models.
    :param node_names: List of str with the names of the nodes. The amount of names will determine the amount of nodes.
    :param link_noise: A number between 0 and 1 that indicates how noisy the generated EPR pairs are.
    :param qdevice_noise: A number between 0 and 1 that indicates how noisy the qubit operations on the nodes are.
    :param qdevice_depolar_time: The timescale, in nanoseconds, for depolarizing noise for qubits on the memory.
    :param qdevice_op_time: The time, in nanoseconds,
     for various operations, such as gates, measurements and qubit initialization.
    :param clink_delay: The time, in nanoseconds, it takes for the classical message to arrive.
    :param link_delay: The time, in nanoseconds, it takes for an EPR pair to be generated.
    :return: StackNetworkConfig object with a network.
    """

    qdevice_cfg = GenericQDeviceConfig.perfect_config()

    qdevice_cfg.two_qubit_gate_depolar_prob = qdevice_noise
    qdevice_cfg.single_qubit_gate_depolar_prob = qdevice_noise

    qdevice_cfg.T1 = qdevice_depolar_time
    qdevice_cfg.T2 = qdevice_depolar_time

    qdevice_cfg.measure_time = qdevice_op_time
    qdevice_cfg.init_time = qdevice_op_time
    qdevice_cfg.single_qubit_gate_time = qdevice_op_time
    qdevice_cfg.two_qubit_gate_time = qdevice_op_time

    link_cfg = DepolariseLinkConfig(
        fidelity=1 - link_noise * 3 / 4, t_cycle=link_delay, prob_success=1
    )

    clink_cfg = DefaultCLinkConfig(delay=clink_delay)

    return create_complete_graph_network(
        node_names,
        link_typ="depolarise",
        link_cfg=link_cfg,
        clink_typ="default",
        clink_cfg=clink_cfg,
        qdevice_typ="generic",
        qdevice_cfg=qdevice_cfg,
    )


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
    """Create a star type network with a metro hub in the center."""
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])
    clink_cfg = InstantCLinkConfig() if clink_cfg is None else clink_cfg

    node_names = [f"node_{i}" for i in range(num_nodes)]
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

    mh_connections = []
    node_distances = (
        [node_distances for _ in range(num_nodes)]
        if not isinstance(node_distances, list)
        else node_distances
    )
    for node_name, dist in zip(node_names, node_distances):
        mh_connections.append(MetroHubConnectionConfig(stack=node_name, length=dist))

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
