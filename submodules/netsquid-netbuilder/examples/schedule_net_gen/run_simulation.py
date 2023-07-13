from netsquid_magic.models.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.test_utils.network_generation import create_metro_hub_network
from protocols import AliceProtocol, BobProtocol

import squidasm

num_nodes = 10
link_cfg = DepolariseLinkConfig(fidelity=0.9, prob_success=0.05, t_cycle=20)

cfg = create_metro_hub_network(
    num_nodes,
    node_distances=1,
    link_typ="depolarise",
    link_cfg=dict(link_cfg),
    clink_typ="default",
    clink_cfg=dict(DefaultCLinkConfig()),
)
num_epr_pairs = 3

builder = get_default_builder()
network = builder.build(cfg, hacky_is_squidasm_flag=False)

protocol_mapping = {}
for i, node in enumerate(cfg.stacks):
    if i % 2 == 0:
        peer_name = cfg.stacks[i + 1].name
        prot = AliceProtocol(peer=peer_name, num_epr_pairs=num_epr_pairs)
    else:
        peer_name = cfg.stacks[i - 1].name
        prot = BobProtocol(peer=peer_name, num_epr_pairs=num_epr_pairs)
    protocol_mapping[node.name] = prot

sim_stats = run(network, protocol_mapping)
print(sim_stats)
