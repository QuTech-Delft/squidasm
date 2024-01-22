import logging

import numpy.random
from application import ClientProgram, ServerProgram
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.util.network_generation import create_complete_graph_network

from squidasm.run.stack.run import run

num_nodes = 6
random_request_start_times = False
node_names = [f"Node_{i}" for i in range(num_nodes)]

cfg = create_complete_graph_network(
    node_names,
    "perfect",
    PerfectLinkConfig(state_delay=100),
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(delay=100),
)

server_name = node_names[0]
client_names = node_names[1:]

programs = {server_name: ServerProgram(clients=client_names)}
for client in client_names:
    programs[client] = ClientProgram(client, server_name)

# Set log level for all programs
for program in programs.values():
    program.logger.setLevel(logging.INFO)

if random_request_start_times:
    # Set the clients to start their requests at a random time between 0 and 400 ns
    for client in client_names:
        programs[client].request_start_time = numpy.random.randint(0, 400)

run(config=cfg, programs=programs, num_times=1)
