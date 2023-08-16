from application import ClientProgram, ServerProgram
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.test_utils.network_generation import create_multi_node_network

from squidasm.run.stack.run import run

num_nodes = 6
# import network configuration from file
cfg = create_multi_node_network(
    num_nodes,
    "perfect",
    PerfectLinkConfig(state_delay=100),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(delay=100),
)

node_names = [stack.name for stack in cfg.stacks]
server_name = node_names[0]
client_names = node_names[1:]
# Create instances of programs to run

programs = {server_name: ServerProgram(clients=client_names)}
for client in client_names:
    programs[client] = ClientProgram(client, server_name)

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(config=cfg, programs=programs, num_times=1)
