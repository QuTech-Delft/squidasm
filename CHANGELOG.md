CHANGELOG
=========

2023-04-06 (0.11.0)
------------------
- Added documentation, specifically a tutorial for readthedocs
- Hotfix for heralded connection resulting EPR pairs not in Phi+ state
- Changed parameters in configuration to use float instead of int
- Removed parameters argument in ProgramMeta

2022-11-14 (0.10.0)
------------------
- Made compatible with NetQASM 0.12.1.

2022-05-23 (0.9.0)
------------------
- Made compatible with NetQASM 0.11.

2022-04-07 (0.8.4)
------------------
- Updated versions of dependencies to prevent installation conflicts.

2021-11-15 (0.8.3)
------------------
- Use MIT license.

2021-10-06 (0.8.2)
------------------
- Made compatible with NetQASM 0.8.4.
- Improve configuration format for stack simulator.
- Add depolarizing and heralded link types to stack simulator.
- Added stack logger as alternative to netqasm logger.

2021-09-20 (0.8.1)
------------------
- Fixes in MANIFEST.in and setup.py

2021-09-19 (0.8.0)
------------------
- Package reorganization.
- Fixed various bugs in stack simulator.
- Made compatible with NetQASM 0.8.0.


2021-09-10 (0.7.2)
------------------
- Package intallation now uses `pyproject.toml`.

2021-07-14 (0.7.1)
------------------
- Single-thread simulator now allows app inputs.

2021-05-10 (0.7.0)
------------------
- Compatible with `netqasm` 0.7.2, see [`netqasm` CHANGELOG](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md).

2021-02-10 (0.6.0)
------------------
- Compatible with `netqasm` 0.6.0, see [`netqasm` CHANGELOG](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md).

2021-01-25 (0.5.1)
------------------
- Fix a bug where all nodes use the same noise parameters as the node defined last in `network.yaml`.

2020-12-17 (0.5.0)
------------------
- Using `netqasm` 0.5.0, see [`netqasm` CHANGELOG](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md).

2020-11-20 (0.4.0)
------------------
- Using `netqasm` 0.4.0, see [`netqasm` CHANGELOG](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md).

2020-10-08 (0.3.0)
------------------
- Using `netqasm` 0.2.0, see [`netqasm` CHANGELOG](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md).

2020-09-25 (0.2.0)
------------------
- CLI has now moved to `netqasm`.
  See [changelog](https://github.com/QuTech-Delft/netqasm/blob/develop/CHANGELOG.md) there for details.

2020-09-23 (0.1.0)
------------------
- There is now a distinction between `app_name`s (roles) and `node_name`s (physical locations).
- Proper NV gates.
- Reflects changes in `netqasm` 0.0.12.

2020-09-22 (0.0.8)
------------------
- Reflects changes in `netqasm` 0.0.11.

2020-09-09 (0.0.7)
------------------
- Instrs-logging now include qubit IDs and qubit states for all qubits involved in the operation.
- Instrs-logging now include what to specify what qubits have at some point interacted in the simulaton.

2020-08-27 (0.0.6)
------------------
- Fix bug in `examples/run_examples.py`

2020-08-27 (0.0.5)
------------------
- Support `flavour` specification.
- Use `netqasm` 0.0.7

2020-07-09 (0.0.4)
------------------
- Allow lib-dirs to be None.
- Use `netqasm` 0.0.6

2020-07-09 (0.0.3)
------------------
- Improvements in message queue handling.
- Debug function to be able to extract state in SDK.
- Network config file.
- Using `netqasm` 0.0.4.
- Added applications
  - Distributed CNOT.
  - Blind quantum computing.
  - Anonymous transfer.
  - CHSH using repeater.

2020-05-20 (0.0.2)
------------------
- Now using netqasm 0.0.4
- Added applications
  - teleport
  - magic square
  - BB84

2020-05-06 (0.0.1)
------------------
- Now using netqasm 0.0.1

2020-02-15 (0.0.0)
------------------
- Created this package
