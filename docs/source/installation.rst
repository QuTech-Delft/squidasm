.. _label_installation:

Installation
============
SquidASM uses the `NetSquid <https://netsquid.org/>`_ Python package.
To install and use NetSquid, you need to first create an account for it.
The username and password for this account are also needed to install `squidasm`.

Because NetSquid only supports Linux and MacOS, SquidASM also requires a Linux or MacOS system.
For Windows users it is recommended to either use a virtual machine or use `Windows Subsystem for Linux (WSL) <https://learn.microsoft.com/en-us/windows/wsl/install>`_.

TODO: we need to describe that you need to clone the repo if you want to do the make and have the examples.

The SquidASM install script requires the NetSquid user name and password to be set into environment variables.
This can be done by executing:

.. code-block:: bash

    export NETSQUIDPYPI_USER={your NetSquid forum user name}
    export NETSQUIDPYPI_PWD={your NetSquid forum password}

For a more permanent solution, if SquidASM is installed more than once, these lines can be added to ``~\.bashrc``.

Then, to install squidasm do:

.. code-block:: bash

   make install

To verify the installation, do:

.. code-block:: bash

   make verify
