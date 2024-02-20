import logging

import netsquid as ns
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig
from netsquid_driver.logger import SnippetLogManager
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.util.network_generation import create_qia_prototype_network
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
SnippetLogManager.set_log_level(logging.INFO)

builder = get_default_builder()
cfg = create_qia_prototype_network(
    nodes_hub1=2,
    nodes_hub2=2,
    num_nodes_repeater_chain=2,
    node_distances_hub1=5,
    node_distances_hub2=5,
    node_distances_repeater_chain=20,
    link_typ="perfect",
    link_cfg=PerfectLinkConfig(speed_of_light=1e9),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
)
network = builder.build(cfg)


sim_stats = run(
    network,
    {
        "hub1_node_0": AliceProtocol("hub2_node_0"),
        "hub2_node_0": BobProtocol("hub1_node_0"),
    },
)
print(sim_stats)
