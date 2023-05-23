from typing import Generator

import netsquid as ns
from blueprint.base_configs import StackNetworkConfig
from blueprint.setup_network import NetworkBuilder, ProtocolController
from squidasm.run.stack.run import run
from squidasm.sim.stack.egp import EgpProtocol
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
cfg = StackNetworkConfig.from_file("config.yaml")

network = NetworkBuilder.build(cfg)

alice = AliceProtocol(network.get_protocol_context("Alice"))
bob = BobProtocol(network.get_protocol_context("Bob"))


alice.start()
bob.start()
ProtocolController.start_all()
sim_stats = ns.sim_run()
print(sim_stats)

