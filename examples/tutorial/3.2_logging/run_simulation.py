import sys

import netsquid as ns
from application import AliceProgram, BobProgram
from netsquid_netbuilder.base_configs import NetworkConfig

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager

# Fix seed on test runs to avoid accidentally triggering the "error" in this example
if "--test_run" in sys.argv:
    ns.set_random_state(seed=42)

# import network configuration from file
cfg = NetworkConfig.from_file("config.yaml")

# Set log level
LogManager.set_log_level("INFO")
# Disable logging to terminal
logger = LogManager.get_stack_logger()
logger.handlers = []
# Enable logging to file
LogManager.log_to_file("info.log")


# Create instances of programs to run
message = [0, 1, 1, 0, 0]
alice_program = AliceProgram(message)
bob_program = BobProgram()

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
_, bob_results = run(
    config=cfg, programs={"Alice": alice_program, "Bob": bob_program}, num_times=1
)

message_received = bob_results[0]["received message"]
errors = [int(sent != received) for sent, received in zip(message, message_received)]

print(
    f"sent message:     {message}\n"
    f"received message: {message_received}\n"
    f"errors:           {errors}"
)
