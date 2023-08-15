
# Contents
The examples in this folder are based on applications in the community application library of the Quantum Network Explorer: [Quantum Network Explorer Applications](https://www.quantum-network.com/applications/).
The theory and full description of these applications can be found on the Quantum Network Explorer website.

## Quantum Key Distribution
Quantum key distribution is a scheme designed to produce a shared secret key between two parties.
[Learn More](https://www.quantum-network.com/applications/5/)

In the example_qkd.py file the qkd protocol is demonstrated.
In this protocol the number of EPR pairs used for secret key generation may be specified,
and it will return a raw key and an estimate of the error rate.
In this example, we have enabled some noise in the EPR pair generation,
so the secret key will not perfectly match between the two parties.

In example_use_qkd.py an example of how to use the pre-made routine of a QKD protocol in an application is demonstrated.

## State Teleportation
Quantum teleportation is a process in which quantum information can be transmitted
from one location to another. [Learn More](https://www.quantum-network.com/applications/1/)

The folder contains an example that shows the internal workings of the teleportation routine 
as well as another example how to use the pre-made routine.

## Distributed gate
Performs a controlled two qubit operation distributed over two nodes: Controller and Target.
Controller owns the control qubit, and Target owns the target qubit.
[Learn More](https://www.quantum-network.com/applications/7/)

The folder contains an example that shows the internal workings of a distributed CNOT routine 
as well as another example how to use the pre-made routines.

## Blind Quantum Computing
Blind Quantum Computing refers to a set of protocols in which a client with limited computational resources
delegates a computation to a more powerful server.
The server is blind to the specific quantum computation it is performing.
[Learn More](https://www.quantum-network.com/applications/11/)

## CHSH
CHSH is a pseudo-telepathy game in which Alice and Bob can reach a better winning probability by employing a quantum strategy.
[Learn More](https://www.quantum-network.com/applications/14/)

## Magic Square
Magic square is a pseudo-telepathy game in which two players attempt to fill out a square according to certain rules.
You can always win this game if you use a quantum strategy!
[Learn More](https://www.quantum-network.com/applications/13/)

