from typing import Generator

import netsquid as ns
from blueprint.base_configs import StackNetworkConfig
from blueprint.network_builder import NetworkBuilder
from squidasm.run.stack.run import run
from squidasm.sim.stack.egp import EgpProtocol
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
cfg = StackNetworkConfig.from_file("config.yaml")

builder = NetworkBuilder()
network = builder.build(cfg)

alice = AliceProtocol(network.get_protocol_context("Alice"))
bob = BobProtocol(network.get_protocol_context("Bob"))


alice.start()
bob.start()
builder.protocol_controller.start_all()
sim_stats = ns.sim_run()
print(sim_stats)

