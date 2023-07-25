import os

import numpy as np
from application import AliceProgram, BobProgram

from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Find all configuration files in the same directory as this file
files = os.listdir()
config_files = [file for file in files if ".yaml" in file]
config_files.sort()

for config_file in config_files:

    # import network configuration from file
    cfg = StackNetworkConfig.from_file(config_file)

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

    print(f"Results for configuration file: {config_file}")
    print(
        f"average error rate: {sum(errors) / len(errors) * 100: .1f}% using {len(errors)} epr requests"
    )
    print(f"average value Alice: {sum(results_alice) / len(results_alice)}")
    print(f"average value Bob: {sum(results_bob) / len(results_bob)}")
