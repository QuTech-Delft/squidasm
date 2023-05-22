import numpy as np
import os

from application import AliceProgram, BobProgram
from blueprint.base_configs import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager

# Find all configuration files in the same directory as this file
files = os.listdir()
config_files = [file for file in files if ".yaml" in file]
config_files.sort()


# Set log level
LogManager.set_log_level("INFO")
# Disable logging to terminal
logger = LogManager.get_stack_logger()
logger.handlers = []
# Enable logging to fileZ
LogManager.log_to_file("info.log")
cfg = StackNetworkConfig.from_file("config.yaml")

xvals = []
yvals = []
yvals2 = []
diff = []

for x in np.arange(0, 1, 0.05):

    # import network configuration from file
    stack = cfg.stacks[0]
    stack.qdevice_cfg["two_qubit_gate_depolar_prob"] = x

    # Set a parameter, the number of epr rounds, for the programs
    epr_rounds = 200
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    # return from run method are the results per node
    simulation_iterations = 20
    raw, _ = run(config=cfg,
                                     programs={"Alice": alice_program, "Bob": bob_program},
                                     num_times=simulation_iterations)

    # results have List[Dict[]] structure. List contains the simulation iterations
    results_alice = [raw[i]["measurements"] for i in range(simulation_iterations)]
    meas2 = [raw[i]["meas2"] for i in range(simulation_iterations)]


    # Create one large list of all EPR measurements
    results_alice = np.concatenate(results_alice).flatten()
    meas2 = np.concatenate(meas2).flatten()

    # Per EPR determine if results are identical
    errors = results_alice

    yvals.append(sum(results_alice) / len(results_alice) * 100)
    yvals2.append(sum(meas2) / len(meas2) * 100)
    diff.append(sum(np.abs(np.subtract(meas2, results_alice)))/ len(results_alice) * 100)
    xvals.append(x)

from matplotlib import pyplot

pyplot.plot(xvals, yvals, label="avg q1")

pyplot.plot(xvals, yvals2, label="avg q2")

pyplot.plot(xvals, diff, label="avg q1!=q2")
pyplot.xlabel("prob")
pyplot.ylabel("percentage")
pyplot.legend()
pyplot.savefig("two_gate_diff.png")
