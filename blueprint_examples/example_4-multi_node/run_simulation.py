import netsquid as ns
import numpy as np
from matplotlib import pyplot

from blueprint.base_configs import StackNetworkConfig
from blueprint.links.perfect import PerfectLinkConfig
from blueprint.clinks.default import DefaultCLinkConfig
from blueprint.network_builder import NetworkBuilder
from blueprint_examples.network_generation import create_multi_node_network
from protocols import ServerProtocol, ClientProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
num_nodes = 5

builder = NetworkBuilder()
cfg = create_multi_node_network(num_nodes, "perfect", PerfectLinkConfig(),
                                clink_typ="default", clink_cfg=DefaultCLinkConfig(delay=100))
network = builder.build(cfg, hacky_is_squidasm_flag=False)

clients = [f"node_{i}" for i in range(1, num_nodes)]

server = ServerProtocol(network.get_protocol_context("node_0"), clients)
client_programs = [ClientProtocol(network.get_protocol_context(client), "node_0") for client in clients]

server.start()
for client_program in client_programs:
    client_program.start()
builder.protocol_controller.start_all()
sim_stats = ns.sim_run()
print(sim_stats)

