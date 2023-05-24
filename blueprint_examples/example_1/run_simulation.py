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

qubit_alice = network.nodes["Alice"].qdevice.peek(0)[0]
qubit_bob = network.nodes["Bob"].qdevice.peek(0)[0]

reference_state = ns.qubits.ketstates.b00
fidelity = ns.qubits.qubitapi.fidelity([qubit_alice, qubit_bob], reference_state)
print(fidelity)

print(sim_stats)

