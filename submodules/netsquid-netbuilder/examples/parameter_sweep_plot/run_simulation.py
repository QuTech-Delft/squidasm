import netsquid as ns
import numpy as np
from matplotlib import pyplot
from netsquid_magic.models.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_netbuilder.run import get_default_builder, run
from netsquid_netbuilder.util.network_generation import create_2_node_network
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
builder = get_default_builder()


def run_simulation(cfg: NetworkConfig) -> float:
    network = builder.build(cfg)

    alice = AliceProtocol()
    bob = BobProtocol()

    run(network, {"Alice": alice, "Bob": bob})

    qubit_alice = network.end_nodes["Alice"].qdevice.peek(0)[0]
    qubit_bob = network.end_nodes["Bob"].qdevice.peek(0)[0]

    reference_state = ns.qubits.ketstates.b00
    fidelity = ns.qubits.qubitapi.fidelity([qubit_alice, qubit_bob], reference_state)
    builder.protocol_controller.stop_all()
    return fidelity


link_config = DepolariseLinkConfig.from_file("config.yaml")
link_fidelities = np.arange(0.5, 1, 0.1)
measured_fidelity = []
num_average = 100

for link_fidelity in link_fidelities:
    link_config.fidelity = link_fidelity
    config = create_2_node_network("depolarise", link_config)

    measure_list = [run_simulation(config) for _ in range(num_average)]
    measured_fidelity.append(np.average(measure_list))

pyplot.plot(link_fidelities, measured_fidelity)
pyplot.savefig("out.png")
