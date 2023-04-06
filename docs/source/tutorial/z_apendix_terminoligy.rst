
Terminology
==============

``Program``
    Part of an application, but refers to the code being executed on one node.
    For example BQC is an application, but it consists of two programs, one program for the client and another for the server.

``Application``
    A collection of Programs on multiple nodes working together to achieve a certain result.

``quantum network processing unit (QNPU)``
    The software and device that are responsible for both operations on local qubits as well as creating EPR pairs with remote nodes.
    The software is sent these instructions using the `NetQASM language <https://github.com/QuTech-Delft/netqasm>`_.
    An example of the software is QNodeOS.

``Host``
    The device running a program. This can be any type of classical computer.
    This is one of the highest layers of the stack of an end node.
    The host runs a quantum internet application by sending instructions to the Quantum network controller.

