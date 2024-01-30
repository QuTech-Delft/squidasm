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
    RepeaterChainConfig,
)
from netsquid_magic.photonic_interface_interface import IPhotonicInterfaceConfig
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
    """
    Create a complete graph network configuration.
    :param node_names: List of str with the names of the nodes. The amount of names will determine the amount of nodes.
    :param link_typ: str specification of the link model to use for quantum links.
    :param link_cfg: Configuration of the link model.
    :param clink_typ: str specification of the clink model to use for classical communication.
    :param clink_cfg: Configuration of the clink model.
    :param qdevice_typ: str specification of the qdevice model to use for quantum devices.
    :param qdevice_cfg: Configuration of qdevice.
    :return: StackNetworkConfig object with a network.
    """
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
    node_names: List[str],
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
    """Create a star type network with a metro hub in the center.
    :param node_names: List of str with the names of the nodes. The amount of names will determine the amount of nodes.
    :param node_distances: List of float or float with distances for each end-node to the central hub.
    :param link_typ: str specification of the link model to use for quantum links.
    :param link_cfg: Configuration of the link model.
    :param schedule_typ: str specification of the schedule model to use for the metro hub.
    :param schedule_cfg: Configuration of the schedule to use.
    :param clink_typ: str specification of the clink model to use for classical communication.
    :param clink_cfg: Configuration of the clink model.
    :param qdevice_typ: str specification of the qdevice model to use for quantum devices.
    :param qdevice_cfg: Configuration of qdevice.
    :return: StackNetworkConfig object with a network.

    """
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])
    clink_cfg = InstantCLinkConfig() if clink_cfg is None else clink_cfg

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

    mh_connections = connect_mh(node_distances, node_names)

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
    node_distances: Union[float, List[float]], node_names: List[str]
) -> List[MetroHubConnectionConfig]:
    mh_connections = []
    if not isinstance(node_distances, list):
        node_distances = [node_distances] * len(node_names)
    assert len(node_names) == len(node_distances)

    for node_name, dist in zip(node_names, node_distances):
        mh_connections.append(MetroHubConnectionConfig(stack=node_name, length=dist))

    return mh_connections




def create_qia_prototype_network(
    nodes_hub1: Union[int, List[str]],
    node_distances_hub1: Union[float, List[float]],
    nodes_hub2: Union[int, List[str]],
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
    photonic_interface_typ: str = None,
    photonic_interface_cfg: IPhotonicInterfaceConfig = None,
) -> StackNetworkConfig:
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])
    clink_cfg = InstantCLinkConfig() if clink_cfg is None else clink_cfg

    if isinstance(nodes_hub1, int):
        hub1_node_names = [f"hub1_node_{i}" for i in range(nodes_hub1)]
    else:
        hub1_node_names = nodes_hub1

    if isinstance(nodes_hub2, int):
        hub2_node_names = [f"hub2_node_{i}" for i in range(nodes_hub2)]
    else:
        hub2_node_names = nodes_hub2

    for node_name in hub1_node_names + hub2_node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg=qdevice_cfg)
        network_config.stacks.append(stack)

    mh1_connections = connect_mh(node_distances_hub1, hub1_node_names)
    mh2_connections = connect_mh(node_distances_hub2, hub2_node_names)

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
        f"r{i}" for i in range(num_nodes_repeater_chain)
    ]
    repeater_stacks = []
    for node_name in repeater_node_names:
        qdevice_cfg = (
            GenericQDeviceConfig.perfect_config()
            if qdevice_cfg is None
            else qdevice_cfg
        )
        stack = StackConfig(name=node_name, qdevice_typ=qdevice_typ, qdevice_cfg=qdevice_cfg)
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
        photonic_interface_typ=photonic_interface_typ,
        photonic_interface_cfg=photonic_interface_cfg
    )
    network_config.repeater_chains = [repeater_chain]

    return network_config
