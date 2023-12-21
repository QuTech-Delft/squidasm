from application import ClientProgram, ServerProgram
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.util.network_generation import create_complete_graph_network

from squidasm.run.stack.run import run

num_nodes = 6
node_names = [f"Node_{i}" for i in range(num_nodes)]

# import network configuration from file
cfg = create_complete_graph_network(
    node_names,
    "perfect",
    PerfectLinkConfig(state_delay=100),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(delay=100),
)

server_name = node_names[0]
client_names = node_names[1:]
# Create instances of programs to run

programs = {server_name: ServerProgram(clients=client_names)}
for client in client_names:
    programs[client] = ClientProgram(client, server_name)

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(config=cfg, programs=programs, num_times=1)
