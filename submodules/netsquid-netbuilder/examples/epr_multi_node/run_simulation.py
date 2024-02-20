import netsquid as ns
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.util.network_generation import create_complete_graph_network
from protocols import ClientProtocol, ServerProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
node_names = [f"node_{i}" for i in range(10)]

builder = get_default_builder()
cfg = create_complete_graph_network(
    node_names,
    "perfect",
    PerfectLinkConfig(),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(delay=100),
)
network = builder.build(cfg)

clients = node_names[1:]

server = ServerProtocol(clients)
clients = {client: ClientProtocol("node_0") for client in clients}

sim_stats = run(network, clients | {"node_0": server})
print(sim_stats)
