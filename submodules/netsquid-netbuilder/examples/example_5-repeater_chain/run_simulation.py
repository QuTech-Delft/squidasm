import netsquid as ns
from cprotocols import AliceProtocol, BobProtocol
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.test_utils.network_generation import (
    create_qia_prototype_network,
)

ns.set_qstate_formalism(ns.QFormalism.DM)

builder = get_default_builder()
cfg = create_qia_prototype_network(
    num_nodes_hub1=1,
    num_nodes_hub2=1,
    num_nodes_repeater_chain=2,
    node_distances_hub1=5,
    node_distances_hub2=5,
    node_distances_repeater_chain=20,
    link_typ="perfect",
    link_cfg=PerfectLinkConfig(),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(),
)
network = builder.build(cfg, hacky_is_squidasm_flag=False)


sim_stats = run(
    network,
    {
        "hub1_node_0": AliceProtocol("hub2_node_0"),
        "hub2_node_0": BobProtocol("hub1_node_0"),
    },
)
print(sim_stats)
