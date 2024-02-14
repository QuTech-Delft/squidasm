from application import AliceProgram, BobProgram
from netsquid_netbuilder.base_configs import NetworkConfig

from squidasm.run.stack.run import run

# import network configuration from file
cfg = NetworkConfig.from_file("config.yaml")

# Create instances of programs to run
alice_program = AliceProgram()
bob_program = BobProgram()

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(config=cfg, programs={"Alice": alice_program, "Bob": bob_program}, num_times=1)
