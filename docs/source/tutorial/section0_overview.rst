.. _label_start_tutorial:

*****************
Overview
*****************
Welcome to the SquidASM tutorial.
In this tutorial you will be introduced to the objects and concepts necessary to develop applications and evaluate applications using the SquidASM simulation.

In order to start the tutorial it is recommended to first install SquidASM and the required components. This process is described in :ref:`label_installation`.

The tutorial sections are accompanied by code examples in the SquidASM package that are located in ``examples/tutorial`` folder of SquidASM.
The code examples shown in this tutorial are part of these examples.
It is may be useful to browse through the examples when reading the tutorial to obtain the full context of the snippets.

Files
==========
A simulation of a quantum network application has roughly three components: the network, the application and the simulation.
In order to encourage modularity we split the code into three separate files, in line with the conceptual components:

``application.py``
    This file contains the individual programs that run on end nodes.
    So it will typically contain the AliceProgram and BobProgram or the ServerProgram and ClientProgram.

``config.yaml``
    The file that specifies the network.
    It controls the network layout and end node labels. Moreover, it specifies the link and node types and properties.

``run_simulation.py``
    The executable file that will run the simulation.
    In its most simple form it loads the programs from ``application.py`` and the network from ``config.yaml`` and then runs the simulation.
    In more advanced form it may specify various simulation settings, automate multiple simulation runs and handle the simulation output.

This tutorial will introduce the concepts and files one by one.
The :ref:`first<label_tutorial_basics>` and :ref:`second<label_netqasm>` section will focus exclusively on ``application.py``.
The :ref:`third<label_program_interface>` section will explain ``run_simulation.py``.
The :ref:`fourth<label_network_configuration>` section will explain the network specification using the ``config.yaml`` file.

NetQASM
=========
The applications for SquidASM need to be written almost entirely using the `NetQASM SDK <https://github.com/QuTech-Delft/netqasm>`_ package.
NetQASM has its own documentation, with a `tutorial <https://netqasm.readthedocs.io/en/latest/quickstart.html>`_ and `API documentation <https://netqasm.readthedocs.io/en/latest/netqasm.sdk.html>`_.
We do not recommend starting with the NetQASM tutorial,
as there are differences in syntax between what the NetQASM tutorial introduces and what SquidASM requires from its applications.
Thus this tutorial, in the first two sections, will be introducing NetQASM as well.

While we suggest avoiding the NetQASM tutorial initially, as it will likely cause confusion,
we do recommend using the NetQASM API documentation after completing the tutorial.

