SquidASM
++++++++++++

.. image:: .github/banner.jpg
   :align: center

.. installation-start-inclusion-marker-do-not-remove

Installation
============
SquidASM uses the `NetSquid <https://netsquid.org/>`_ Python package.
To install and use NetSquid, you need to first create an account for the `netsquid forum <https://forum.netsquid.org/ucp.php?mode=register>`_.
The username and password for this account are needed to install SquidASM.

Because NetSquid only supports Linux and MacOS, SquidASM also requires a Linux or MacOS system.
For Windows users it is recommended to either use a virtual machine or
use `Windows Subsystem for Linux (WSL) <https://learn.microsoft.com/en-us/windows/wsl/install>`_.

Next the SquidASM repository needs to be cloned using git.
If git is not installed, instructions on installing it can be found on this `website <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_.
Afterward, go to your desired directory and execute:

.. code-block:: bash

    git clone https://github.com/QuTech-Delft/squidasm.git

This will create a new folder with the name squidasm and download the squidasm package to that folder.

The SquidASM install script requires the NetSquid user name and password to be set into environment variables.
This can be done by executing the following code, but with your own user name and password:

.. code-block:: bash

    export NETSQUIDPYPI_USER=user1234
    export NETSQUIDPYPI_PWD=password1234

It's also possible to write your password to a text file instead, and set the path to that file with another environment variable:

.. code-block:: bash

    export NETSQUIDPYPI_USER=user1234
    export NETSQUIDPYPI_PWD_FILEPATH=password.txt

For a more permanent solution, if SquidASM is installed more than once, these lines can be added to ``~\.bashrc``.

Then, to install squidasm execute the following command inside the newly created squidasm folder:

.. code-block:: bash

   make install

To verify the installation, do:

.. code-block:: bash

   make verify

If this commands completes without errors, it means that SquidASM has been successfully installed and should work properly.

.. note::
    SquidASM can be installed installed inside a virtual environment for python.
    This can be done by activating the virtual environment before the command ``make install``.

    Virtual environments allow a user to install python packages in such a way
    that the installed package and its dependencies are kept separate from the "base" python and other projects.
    For example, with SquidASM this would prevent the SquidASM installation from
    changing the NetSquid version in another project and vice versa.
    For more information regarding virtual environments and how to use them see: https://docs.python.org/3/library/venv.html.


.. installation-end-inclusion-marker-do-not-remove

Getting started
================
A tutorial introducing SquidASM and API documentation can be found on https://squidasm.readthedocs.io/en/latest/index.html.


Simulator variants
=====================
SquidASM currently has 3 ways of simulating applications: ``multithread``, ``singlethread`` and ``stack``. Each of these can run applications written using the NetQASM SDK, but the way they must be written, and what kind of results they can give, is slightly different.

Multithread
-------------
Multithreaded simulation uses multiple threads: one thread for each application layer of each node, plus one thread for the NetSquid simulation of all quantum memories and links of all nodes combined.

Since application layer code is in a separate thread, it can do blocking operations, e.g. waiting for user input or receiving a message over TCP, without blocking the reset of the simulation. The way applications are written for the multithread simulator is hence closest to how they would be written when running on real hardware.

Since the quantum simulator (i.e. NetSquid) uses simulated time and does not work well with real-time interaction (like waiting for events outside the simulator process), the multithreaded simulator uses busy loops in some cases, which slows down overall execution.

Singlethread
-------------
Singlethreaded simulation uses a single thread that runs all application layer code of all nodes as well as all quantum simulation. All communication and classical events are also simulated in NetSquid, in contrast to the multithread simulator. This leads to faster simulation but poses some constraints to how applications are written.

The singlethread simulator is being deprecated in favor of the ``stack`` simulator.

Stack
-------------

The ``stack`` simulator is also singlethreaded, but does more accurate simulation of the components of the software stack that is intended to be run on physical quantum networks.


Usage
=========

Multithread simulator
-------------------------
The multithread simulator is used as one of the backends of the ``netqasm`` package.
See the ``netqasm`` package for more documentation on how to write NetQASM applications and run them using SquidASM.

Stack simulator
----------------

The main interface for the stack simulator is the ``run`` function in ``squidasm.run.stack.run``. See ``examples/stack`` for examples of using the stack simulator.


Implementation
================

The code is divided into the following modules:

* ``nqasm``: implementations of interfaces defined in the ``netqasm`` package
* ``run``: code for setting up and starting simulations
* ``sim``: internal simulation code
* ``util``: various utility functions


License and patent
===================
A patent application (NL 2029673) has been filed which covers parts of the
software in this repository. We allow for non-commercial and academic use but if
you want to explore a commercial market, please contact us for a license
agreement.


Development
===============

For code formatting, ``black`` and ``isort`` are used.
Type hints should be added as much as possible.

Before code is pushed, make sure that the ``make lint`` command succeeds, which runs ``black``, ``isort`` and ``flake8``.


Contributors
===============
In alphabetical order:

* Axel Dahlberg
* Bart van der Vecht (b.vandervecht[at]tudelft.nl)
* Michaɫ van Hooft (M.K.vanHooft@tudelft.nl)
