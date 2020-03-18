SquidASM (0.0.0)
=====================================================

Welcome to SquidASM's README.

To install the package do:
```sh
make install
```

To verify the installation do:
```sh
make verify
```

Examples
--------

To run a file (`simple_measure.nqasm`) containing the script:
```
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q @0
qalloc q!
init q!
op! q! // this is a comment
meas q! m
beq m 0 EXIT
x q!
EXIT:
// this is also a comment
```
which can be found [here](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/examples/netqasm_files/simple_measure.nqasm), run the following:
```sh
netqasm execute --processor=netsquid simple_measure.nqasm
```
the output can be then be found in the file `simple_measure.out` as triggered by the line `output m` which outputs the register `m`.
