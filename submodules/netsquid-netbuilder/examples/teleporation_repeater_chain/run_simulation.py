import logging

import netsquid as ns

from netsquid_magic.models.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.util.network_generation import create_qia_prototype_network
from protocols import TeleportationSenderProtocol, TeleportationReceiverProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
LogManager.set_log_level(logging.ERROR)

builder = get_default_builder()

qdevice_cfg = GenericQDeviceConfig(
    T1=0,
    T2=0,
    two_qubit_gate_depolar_prob=0,
    init_time=1,
    single_qubit_gate_time=1,
    two_qubit_gate_time=1,
    measure_time=1,
)


link_cfg = DepolariseLinkConfig(speed_of_light=1e9, fidelity=1, prob_success=0.1)

# 70 km between two end nodes on different hubs
cfg = create_qia_prototype_network(
    nodes_hub1=2,
    nodes_hub2=2,
    num_nodes_repeater_chain=2,
    node_distances_hub1=5,
    node_distances_hub2=5,
    node_distances_repeater_chain=20,
    link_typ="depolarise",
    link_cfg=link_cfg,
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
    qdevice_typ="generic",
    qdevice_cfg=qdevice_cfg
)
network = builder.build(cfg, hacky_is_squidasm_flag=False)


sim_stats = run(
    network,
    {
        "hub1_node_0": TeleportationSenderProtocol("hub2_node_0"),
        "hub2_node_0": TeleportationReceiverProtocol("hub1_node_0"),
    },
)
print(sim_stats)