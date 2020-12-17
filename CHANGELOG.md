CHANGELOG
=========

Upcoming
--------

2020-12-17 (0.5.0)
------------------
- Using `netqasm` 0.5.0, see [`netqasm` CHANGELOG](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm/-/blob/master/CHANGELOG.md).

2020-11-20 (0.4.0)
------------------
- Using `netqasm` 0.4.0, see [`netqasm` CHANGELOG](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm/-/blob/master/CHANGELOG.md).

2020-10-08 (0.3.0)
------------------
- Using `netqasm` 0.2.0, see [`netqasm` CHANGELOG](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm/-/blob/master/CHANGELOG.md).

2020-09-25 (0.2.0)
------------------
- CLI has now moved to `netqasm`.
  See [changelog](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm/-/blob/master/CHANGELOG.md) there for details.

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
