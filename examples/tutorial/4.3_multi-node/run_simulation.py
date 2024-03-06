from application import AliceProgram, BobProgram, CharlieProgram

from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# import network configuration from file
cfg = StackNetworkConfig.from_file("config.yaml")

alice_program = AliceProgram()
bob_program = BobProgram()
charlie_program = CharlieProgram()


# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(
    config=cfg,
    programs={"Alice": alice_program, "Bob": bob_program, "Charlie": charlie_program},
    num_times=1,
)
