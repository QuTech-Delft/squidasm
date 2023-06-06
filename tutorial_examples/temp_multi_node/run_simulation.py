from application import ServerProgram, ClientProgram
from blueprint.base_configs import StackNetworkConfig
from blueprint.links.perfect import PerfectLinkConfig
from squidasm.run.stack.run import run
from blueprint_examples.network_generation import create_multi_node_network

num_nodes = 6
# import network configuration from file
cfg = create_multi_node_network(num_nodes, "perfect", PerfectLinkConfig())

node_names = [stack.name for stack in cfg.stacks]
server_name = node_names[0]
client_names = node_names[1:]
# Create instances of programs to run

programs = {server_name: ServerProgram(clients=client_names)}
for client in client_names:
    programs[client] = ClientProgram(server_name)

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(config=cfg,
    programs=programs,
    num_times=1)

