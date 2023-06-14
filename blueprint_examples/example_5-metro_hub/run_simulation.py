from typing import Generator

import netsquid as ns
from blueprint.base_configs import StackNetworkConfig
from blueprint.network_builder import NetworkBuilder, ProtocolController
from squidasm.run.stack.run import run
from squidasm.sim.stack.egp import EgpProtocol
from protocols import AliceProtocol, BobProtocol


cfg = StackNetworkConfig.from_file("config_heralded_static.yaml")

builder = NetworkBuilder()
network = builder.build(cfg, hacky_is_squidasm_flag=False)

alice_A = AliceProtocol(network.get_protocol_context("Node1"), peer="Node2")
bob_A = BobProtocol(network.get_protocol_context("Node2"), peer="Node1")

alice_B = AliceProtocol(network.get_protocol_context("Node3"), peer="Node4")
bob_B = BobProtocol(network.get_protocol_context("Node4"), peer="Node3")

alice_A.start()
bob_A.start()
alice_B.start()
bob_B.start()

builder.protocol_controller.start_all()
sim_stats = ns.sim_run()
print(sim_stats)

