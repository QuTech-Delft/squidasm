# QIA Use Case Challenge

## Introduction
Welcome, and we are happy that you decided to participate in the QIA use case challenge!
In this package, we present some examples of applications and utility code that you may find useful for the challenge.

## Requirements
This use case challenge is based around the SquidASM package.
In order to run the examples of this package, an up-to-date installation of SquidASM is required.
The necessary steps to install SquidASM can be found on: [SquidASM Installation Guide](https://squidasm.readthedocs.io/en/latest/installation.html).
Additionally, a tutorial on SquidASM can be found here: [SquidASM Tutorial](https://squidasm.readthedocs.io/en/latest/tutorial/section0_overview.html#).

## Support
For any questions regarding the use case challenge, installation, or SquidASM,
we invite you to ask them on the Slack channel: TODO Slack channel.
Alternatively, questions and comments regarding the installation or SquidASM can also be asked by email: M.K.vanHooft@tudelft.nl

## Contents
The examples in this package are based on applications in the community application library of the Quantum Network Explorer: [Quantum Network Explorer Applications](https://www.quantum-network.com/applications/).
The theory and full description of these applications can be found on the Quantum Network Explorer website.

All the examples can be run via commands: `python qkd.py`, `python state_teleportation.py`, etc.
The code in the examples may be used as inspiration or for implementation in the use case challenge.

### Quantum Key Distribution (qkd.py)
Quantum key distribution is a scheme designed to produce a shared secret key between two parties.
[Learn More](https://www.quantum-network.com/applications/5/)

In the given example, the number of EPR pairs used for secret key generation may be specified,
and it will return a raw key and an estimate of the error rate.
In this example, we have enabled some noise in the EPR pair generation,
so the secret key will not perfectly match between the two parties.

For this use case challenge, one may disable the noise and use the raw key for a desired application,
or one may create an algorithm to distill the secret key into a usable key in the presence of noise.

### State Teleportation (state_teleportation.py)
Quantum teleportation is a process in which quantum information can be transmitted
from one location to another. [Learn More](https://www.quantum-network.com/applications/1/)

### Distributed CNOT (distributed_cnot.py)
Performs a CNOT operation distributed over two nodes: Controller and Target.
Controller owns the control qubit, and Target owns the target qubit.
[Learn More](https://www.quantum-network.com/applications/7/)

### Blind Quantum Computing (bqc.py)
Blind Quantum Computing refers to a set of protocols in which a client with limited computational resources
delegates a computation to a more powerful server.
The server is blind to the specific quantum computation it is performing.
[Learn More](https://www.quantum-network.com/applications/11/)

### CHSH (chsh_game.py)
CHSH is a pseudo-telepathy game in which Alice and Bob can reach a better winning probability by employing a quantum strategy.
[Learn More](https://www.quantum-network.com/applications/14/)

### Magic Square (magic_square.py)
Magic square is a pseudo-telepathy game in which two players attempt to fill out a square according to certain rules.
You can always win this game if you use a quantum strategy!
[Learn More](https://www.quantum-network.com/applications/13/)

### Utilities (util.py)
This file contains utility methods used in the examples and may be utilized in an implementation.
The file contains pieces of protocol, the network generation, and methods for obtaining the qubit state.