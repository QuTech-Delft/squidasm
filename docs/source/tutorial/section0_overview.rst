.. _label_start_tutorial:

*****************
Overview
*****************
Welcome to the SquidASM tutorial. In this tutorial you will be introduced to the objects and concepts necessary to develop applications and evaluate applications using the SquidASM simulation.

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
TODO decide if needed and possibly expand

``Program``
    Part of an application, but refers to the code being executed on one node.

``Application``
    A collection of Programs working together to achieve a certain result.

``Quantum device controller``
    The software that is responsible for both operations on local qubits as well as creating EPR pairs with remote nodes.
    This software is sent these instructions using the `NetQASM language <https://github.com/QuTech-Delft/netqasm>`_.
    An example of such a system is QNodeOS.
