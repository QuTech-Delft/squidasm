.. _label_start_tutorial:

*****************
Overview
*****************
Welcome to the SquidASM tutorial.
In this tutorial you will be introduced to the objects and concepts necessary to develop applications and evaluate applications using the SquidASM simulation.

The applications for SquidASM need to be written using the `NetQASM SDK <https://github.com/QuTech-Delft/netqasm>`_,
but no prior knowledge of NetQASM is required.
Moreover there are differences in syntax between NetQASMs SDK and SquidASM, thus it is advised to follow the tutorial regardless of prior knowledge.

In order to start the tutorial it is recommended to first install SquidASM and the required components. This process is described in :ref:`label_installation`.

The tutorial sections are accompanied by code examples in the SquidASM package that are located in ``tutorial_examples``.

Files
==========
The examples for the tutorial typically contain three files:

``application.py``
    This file contains the individual programs that run on end nodes.
    So it will typically contain the AliceProgram and BobProgram or the ServerProgram and ClientProgram.

``config.yaml``
    The file that specifies the network.
    It controls the network layout and end node labels moreover, it specifies the link and node types and properties.

``run_simulation.py``
    The executable file that will run the simulation.
    In its most simple form it loads the programs from ``application.py`` and the network from ``config.yaml`` and then runs the simulation.
    In more advanced form it may specify various simulation settings, automate multiple simulation runs and handle the simulation output.

Terminology
==============

``Program``
    Part of an application, but refers to the code being executed on one node.
    For example BQC is an application, but it consists of two programs, one program for the client and another for the server.

``Application``
    A collection of Programs on multiple nodes working together to achieve a certain result.

``Quantum Network controller``
    The software that is responsible for both operations on local qubits as well as creating EPR pairs with remote nodes.
    This software is sent these instructions using the `NetQASM language <https://github.com/QuTech-Delft/netqasm>`_.
    An example of such a system is QNodeOS.

``Host``
    The device running a program. This can be any type of classical computer.
    This is one of the highest layers of the stack of an end node.
    The host runs a quantum internet application by sending instructions to the Quantum network controller.

