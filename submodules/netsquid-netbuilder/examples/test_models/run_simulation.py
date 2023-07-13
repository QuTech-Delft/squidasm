import netsquid as ns
from netsquid_abstractmodel.abstract_node import AbstractQdeviceBuilder
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.run import get_default_builder, run
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
# Load network config
for config_file in [
    "abstract_node.yaml",
    "heralded_double_click.yaml",
    "heralded_single_click.yaml",
]:
    print(f"\n{config_file}\n")
    cfg = StackNetworkConfig.from_file(config_file)

    # Build network
    builder = get_default_builder()
    builder.register_qdevice("abstract", AbstractQdeviceBuilder)
    network = builder.build(cfg)

    # create protocols for end nodes
    alice = AliceProtocol()
    bob = BobProtocol()

    sim_stats = run(network, {"Alice": alice, "Bob": bob})

    # Look at results
    qubit_alice = network.nodes["Alice"].qdevice.peek(0)[0]
    qubit_bob = network.nodes["Bob"].qdevice.peek(0)[0]

    print(ns.qubits.qubitapi.reduced_dm(qubit_alice.qstate.qubits))

    reference_state = ns.qubits.ketstates.b00
    fidelity = ns.qubits.qubitapi.fidelity([qubit_alice, qubit_bob], reference_state)
    print(fidelity)

    print(sim_stats)
