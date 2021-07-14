# SquidASM (0.7.1)

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
