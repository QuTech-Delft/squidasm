# SquidASM (0.8.2)

This is SquidASM, a simulator based on NetSquid that can execute applications written using NetQASM.

## Installation

To install the package you first need to install the following package:
- [`netqasm 0.8`](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm)

Then run:
```sh
make install
```
to install SquidASM.

Note that this will try to install [NetSquid](https://netsquid.org/) if you don't have it, so for this to work, first set the environment variables `NETSQUIDPYPI_USER` and `NETSQUIDPYPI_PWD` to your user and password on the [NetSquid forum](https://forum.netsquid.org/).


To verify the installation and run all tests and examples:
```sh
make verify
```

## Simulator variants
SquidASM currently has 3 ways of simulating applications: `multithread`, `singlethread` and `stack`. Each of these can run applications written using the NetQASM SDK, but the way they must be written, and what kind of results they can give, is slightly different.

### Multithread
Multithreaded simulation uses multiple threads: one thread for each application layer of each node, plus one thread for the NetSquid simulation of all quantum memories and links of all nodes combined.

Since application layer code is in a separate thread, it can do blocking operations, e.g. waiting for user input or receiving a message over TCP, without blocking the reset of the simulation. The way applications are written for the multithread simulator is hence closest to how they would be written when running on real hardware.

Since the quantum simulator (i.e. NetSquid) uses simulated time and does not work well with real-time interaction (like waiting for events outside the simulator process), the multithreaded simulator uses busy loops in some cases, which slows down overall execution. 

### Singlethread
Singlethreaded simulation uses a single thread that runs all application layer code of all nodes as well as all quantum simulation. All communication and classical events are also simulated in NetSquid, in contrast to the multithread simulator. This leads to faster simulation but poses some constraints to how applications are written.

The singlethread simulator is being deprecated in favor of the `stack` simulator.

### Stack
The `stack` simulator is also singlethreaded, but does more accurate simulation of the components of the software stack that is intended to be run on physical quantum networks.


## Usage

### Multithread simulator
The multithread simulator is used as one of the backends of the `netqasm` package.
See the `netqasm` package for more documentation on how to write NetQASM applications and run them using SquidASM.

### Stack simulator
The main interface for the stack simulator is the `run` function in `squidasm.run.stack.run`. See `examples/stack` for examples of using the stack simulator.


## Implementation
The code is divided into the following modules:
- `nqasm`: implementations of interfaces defined in the `netqasm` package
- `run`: code for setting up and starting simulations
- `sim`: internal simulation code
- `util`: various utility functions

## Development

For code formatting, `black` and `isort` are used.
Type hints should be added as much as possible.

Before code is pushed, make sure that the `make lint` command succeeds, which runs `black`, `isort` and `flake8`.


# Contributors
In alphabetical order:
- Axel Dahlberg
- Bart van der Vecht (b.vandervecht[at]tudelft.nl)