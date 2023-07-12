import squidasm
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.run import run, get_default_builder
from netsquid_netbuilder.logger import LogManager
from protocols import AliceProtocol, BobProtocol
from netsquid_netbuilder.data_collectors import collect_schedule_events

logger = LogManager.get_stack_logger()
LogManager.set_log_level(10)

cfg = StackNetworkConfig.from_file("config_heralded_fifo.yaml")
num_epr_pairs = 10

builder = get_default_builder()
network = builder.build(cfg, hacky_is_squidasm_flag=False)

alice_A = AliceProtocol(peer="Node2", num_epr_pairs=num_epr_pairs)
bob_A = BobProtocol(peer="Node1", num_epr_pairs=num_epr_pairs)
alice_B = AliceProtocol(peer="Node4", num_epr_pairs=num_epr_pairs)
bob_B = BobProtocol(peer="Node3", num_epr_pairs=num_epr_pairs)
schedule_events = collect_schedule_events(network.schedulers.popitem()[1])

sim_stats = run(network, {"Node1": alice_A, "Node2": bob_A, "Node3": alice_B, "Node4": bob_B})

for key, val in schedule_events.items():
    print(key)
    print(val)
print(sim_stats)

