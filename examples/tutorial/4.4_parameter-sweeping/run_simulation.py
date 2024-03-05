import numpy as np
from application import AliceProgram, BobProgram
from matplotlib import pyplot

from squidasm.run.stack.config import (
    DepolariseLinkConfig,
    LinkConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run

# import network configuration from file
cfg = StackNetworkConfig.from_file("config.yaml")

# Create a depolarise link in python
depolarise_config = DepolariseLinkConfig.from_file("depolarise_link_config.yaml")
link = LinkConfig(stack1="Alice", stack2="Bob", typ="depolarise", cfg=depolarise_config)

# Replace link from YAML file with new depolarise link
cfg.links = [link]

link_fidelity_list = np.arange(0.5, 1.0, step=0.05)
error_rate_result_list = []

for fidelity in link_fidelity_list:
    # Set fidelity in depolarise link
    depolarise_config.fidelity = fidelity

    # Set a parameter, the number of epr rounds, for the programs
    epr_rounds = 10
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    # return from run method are the results per node
    simulation_iterations = 20
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=simulation_iterations,
    )

    # results have List[Dict[]] structure. List contains the simulation iterations
    results_alice = [
        results_alice[i]["measurements"] for i in range(simulation_iterations)
    ]
    results_bob = [results_bob[i]["measurements"] for i in range(simulation_iterations)]

    # Create one large list of all EPR measurements
    results_alice = np.concatenate(results_alice).flatten()
    results_bob = np.concatenate(results_bob).flatten()

    # Per EPR determine if results are identical
    errors = [
        result_alice != result_bob
        for result_alice, result_bob in zip(results_alice, results_bob)
    ]

    # Write out average error rate
    error_percentage = sum(errors) / len(errors) * 100
    error_rate_result_list.append(error_percentage)

pyplot.plot(link_fidelity_list, error_rate_result_list)
pyplot.xlabel("Fidelity")
pyplot.ylabel("Error percentage")
pyplot.savefig("output_error_vs_fid.png")
