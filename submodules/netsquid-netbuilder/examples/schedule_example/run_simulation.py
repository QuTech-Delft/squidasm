import logging

from example_new_scheduler import ExampleNewScheduleBuilder, ExampleNewScheduleConfig
from netsquid_magic.models.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.data_collectors import collect_schedule_events
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.test_utils.network_generation import create_metro_hub_network
from protocols import AliceProtocol, BobProtocol

# First the network configuration must be constructed
# The individual config objects can be created on by one and their parameters chosen
link_cfg = DepolariseLinkConfig(fidelity=0.9, prob_success=0.05)

# The following method sets up a metro hub configuration
cfg = create_metro_hub_network(
    nodes=10,
    node_distances=10,
    link_typ="depolarise",
    link_cfg=link_cfg,
    clink_typ="default",
    clink_cfg=DefaultCLinkConfig(),
    # Here we specify the type of scheduler
    schedule_typ="new_scheduler",
    schedule_cfg=ExampleNewScheduleConfig(error_print_msg="Hello world!!"),
)

# Next we need to make a "real" network from the network configuration
# This is done via a builder.
# Since we have an extra model for the scheduler that the default builder does not know about
# we must register the new model to the builder
builder = get_default_builder()
builder.register_scheduler(key="new_scheduler", builder=ExampleNewScheduleBuilder)
network = builder.build(cfg, hacky_is_squidasm_flag=False)

# We can setup a listener to inspect what events happen with the scheduler
# The scheduler_events is a dictionary with lists of the events for each event type.
# See the docstring of collect_schedule_events for more info
scheduler = network.schedulers["metro hub"]
scheduler_events = collect_schedule_events(scheduler)

# Sets up the protocols
protocol_mapping = {}
num_epr_pairs = 10
for i, node in enumerate(cfg.stacks):
    if i % 2 == 0:
        peer_name = cfg.stacks[i + 1].name
        prot = AliceProtocol(peer=peer_name, num_epr_pairs=num_epr_pairs)
    else:
        peer_name = cfg.stacks[i - 1].name
        prot = BobProtocol(peer=peer_name, num_epr_pairs=num_epr_pairs)
    protocol_mapping[node.name] = prot

# Set logging level
LogManager.set_log_level(logging.INFO)
# Run the simulation
sim_stats = run(network, protocol_mapping)

for key, vals in scheduler_events.items():
    print(f"\nEvent type: {key}\nEvents:")
    print(vals)
