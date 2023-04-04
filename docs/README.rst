How to build the docs
=====================
Install the package as specified in squidasm root README.rst file.
Keep the terminal current directory at the root of SquidASM package for all steps.
Install the extra requirements for building documentation using the commands:

.. code-block:: bash

    pip install .[rtd]

Then build the docs using:

.. code-block:: bash

    make docs html

The html output can be viewed by opening: docs/build/html/index.html
