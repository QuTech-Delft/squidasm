# SquidASM (0.5.0)

Welcome to SquidASM's README.

To install the package you first need to install [`netqasm`](https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm).
Then do:
```sh
make install
```
Note that this will try to install [NetSquid](https://netsquid.org/) if you don't have it, so for this to work, first set the environment variables `NETSQUIDPYPI_USER` and `NETSQUIDPYPI_PWD` to your user and password on the [NetSquid forum](https://forum.netsquid.org/).


To verify the installation do:
```sh
make verify
```

## Examples
Check the folder `examples` for how to program and run netqasm programs.

## CLI
There is a CLI for easily run applications written in Python which produces NetQASM and communicates these to a thread running a NetSquid backend.
To do this, do for example:
```sh
cd examples/apps/teleport
squidasm simulate
```
which will simulate a teleport application between Alice and Bob, defined by the scrips `app_alice.py` and `app_bob.py`, in the folder [`examples/apps/teleport`](https://gitlab.tudelft.nl/qinc-wehner/netqasm/squidasm/tree/master/examples/apps/teleport).
You can a log-record of what quantum operations occured during this simulation in `examples/app/teleport/log`.

Through the CLI you can specify custom paths to application and network configuration as well as logging directory and logging level. To see all options and their description do
```sh
squidasm simulate --help
```

### Configuration
The applications can be configured by yaml-files in the same folder (e.g. `alice.yaml`) which provides arguments to the application, such as how to initialize the state to be teleported.

Furthermore, the underlying simulated physical quantum network can be configured by the yaml-file `network.yaml`, to provide details of quantum operations, their noise and execution time.

### Logging
In the folder `log` of the application folder records of all runs are stored in folders based on the time it was executed.
There is also a folder `LAST` with the latest log-folder for convinience.
A log-folder contains a seperate log-file for each host from the simulation (e.g. `alice.log`).

A line in a log-file looks for example as follows:
```sh
NetQASM.Instr-by-NetSquidExecutioner(alice) : WCT=2020-04-23 12:45:10,482 : NST=13952.0 : SID=0 : PRC=18 : HLN=19 : INS=init : Doing instruction init with operands Q0
```
containing the following fields:
* `WCT` (wall-clock time): Timestamp of computer running the simulation.
* `SIT` (simulated time): Timestamp of NetSquid time (nano-seconds).
* `SID` (subroutine ID): ID of the subroutine (incemental for subroutines sent by app).
* `PRC` (program counter): Which line/instruction this is in the subroutine.
* `HLN` (host line-number): Which line in the host application (e.g. `app_alice.py`) this instrution corresponds to.
* `INS` (instruction): Which instruction it is.

In the log-folder, there are also files containing information about the NETQASM subroutines sent from the host to the backend in the files called for example `subroutines_alice.pkl`.
These files are pickled version of a list of subroutines (which are dataclasses).
