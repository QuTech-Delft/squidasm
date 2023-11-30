This is a changelog that is separate from the main changelog, this is to log changes on the beta branch

2023-TODO (b0.0.4)
-------------------
- Changed signature of create_metro_hub_network method in network_generation.py to use node_names instead of num_nodes as argument
- Added tests for classical communication and EPR generation delays for metro hubs
- Renamed `state_delay` parameter in perfect link model to `delay`
- Changed interplay between `LinkLayer` and `MagicDistributor` so that completion of a delivery in the `LinkLayer` happens on completion of label_delivery and not on state_delivery
- Depolarise model has been edited such that success in the first cycle will have state delivery at half the cycle and label delivery at the end of the cycle

2023-10-26 (b0.0.3)
-------------------
- Expanded tests in regard to checking: classical communication, local gates & decoherence and EPR pair generation
- Fix for incorrect bell state correction of single-click magic distributor
- Disabled decoherence and set gate times to zero in perfect presets of generic and nv qdevices
- Renamed test_utils folder in netsquid_netbuilder to util
- Various changes and renaming to methods in `netsquid_netbuilder.util.network_generation`
- Flagged `create_two_node_network` method in `squidasm.util.util` as deprecated, users are advised to migrate to methods in `netsquid_netbuilder.util.network_generation`
- Added a flag `--test_run` when running examples via `run_examples.py` to indicate a test run of an example
- Fix the netsquid seed in tutorial example 3.2_logging to avoid accidental failure when performing a test run


2023-10-08 (b0.0.2)
------------------
- Merged changes of develop branch from 0.11.0 to 0.12.1
- Bugfix for error when using YAML files for creating metropolitan hubs
- Set gate times to zero for perfect generic config
- Fixed various bugs in schedulers
- Expanded unit tests for schedulers
- Fix for macOS bug
- Added GHZ routine

2023-07-14 (b0.0.1)
------------------
- Added support for multiple end nodes
- Added example for multi-node usage
- Created netsquid-netbuilder package
- Added netsquid-magic and netsquid-abstractmodel as git submodules
- Removed squidasm\run\stack\config.py. The config objects have been moved to netsquid-netbuilder.
- LogManager has been moved from squidASM package to netsquid-netbuilder package
- Added metropolitan hubs with schedulers
- Added classical links
- setting up and running the network for tests in tests\stack now uses shared network setup methods. (shared with non-test network setup)
- Netqasm breakpoint requests are temporarily not supported
