from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_driver.logger import SnippetLogManager
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.util.data_collectors import collect_schedule_events
from protocols import AliceProtocol, BobProtocol

logger = SnippetLogManager.get_logger()
SnippetLogManager.set_log_level(10)

cfg = NetworkConfig.from_file("config_heralded_fifo.yaml")
num_epr_pairs = 10

builder = get_default_builder()
network = builder.build(cfg)

alice_A = AliceProtocol(peer="Node2", num_epr_pairs=num_epr_pairs)
bob_A = BobProtocol(peer="Node1", num_epr_pairs=num_epr_pairs)
alice_B = AliceProtocol(peer="Node4", num_epr_pairs=num_epr_pairs)
bob_B = BobProtocol(peer="Node3", num_epr_pairs=num_epr_pairs)
metro_hub = list(network.hubs.values())[0]
schedule_events = collect_schedule_events(metro_hub.scheduler)

sim_stats = run(
    network, {"Node1": alice_A, "Node2": bob_A, "Node3": alice_B, "Node4": bob_B}
)

for key, val in schedule_events.items():
    print(key)
    print(val)
print(sim_stats)
