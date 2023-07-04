from blueprint.base_configs import StackNetworkConfig
from blueprint.run import run, get_default_builder
from protocols import AliceProtocol, BobProtocol
import squidasm

squidasm.SUPER_HACKY_SWITCH = True

cfg = StackNetworkConfig.from_file("config_heralded_fifo.yaml")
num_epr_pairs = 3

builder = get_default_builder()
network = builder.build(cfg, hacky_is_squidasm_flag=False)

alice_A = AliceProtocol(peer="Node2", num_epr_pairs=num_epr_pairs)
bob_A = BobProtocol(peer="Node1", num_epr_pairs=num_epr_pairs)
alice_B = AliceProtocol(peer="Node4", num_epr_pairs=num_epr_pairs)
bob_B = BobProtocol(peer="Node3", num_epr_pairs=num_epr_pairs)

sim_stats = run(network, {"Node1": alice_A, "Node2": bob_A, "Node3": alice_B, "Node4": bob_B})
print(sim_stats)

