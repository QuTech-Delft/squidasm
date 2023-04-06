Configurations
================
All configurations can all be created via two routes:

#. Directly created using initialization and keyword arguments:

    .. code-block:: python

        depolarise_config = DepolariseLinkConfig(fidelity=0.9)
        link = LinkConfig(stack1="Alice", stack2="Bob", typ="depolarise", cfg=depolarise_config)

#. Loading from a YAML configuration file:

    .. code-block:: python

        cfg = StackNetworkConfig.from_file("config.yaml")

For more details regarding usage patterns of configurations, see the tutorial section: :ref:`label_configuration_file`.

Network Configuration
+++++++++++++++++++++

 .. autoclass:: squidasm.run.stack.config.StackNetworkConfig
    :members:
    :undoc-members:
    :member-order: bysource

Stacks configurations
+++++++++++++++++++++

.. toctree::
    :maxdepth: 2

    configurations/stack_configurations

Link configurations
+++++++++++++++++++++

.. toctree::
    :maxdepth: 2

    configurations/link_configurations