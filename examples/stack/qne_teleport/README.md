## Prerequisites
`squidasm` relies on [NetSquid](https://netsquid.org/).
To install NetSquid, an account is needed. See the NetSquid website how this is done.

### Installation
Clone the squidasm repostitory and checkout the `qne-hardware` branch:
```
git clone https://github.com/QuTech-Delft/squidasm
cd squidasm
git checkout qne-hardware
```

Make sure you have two environment variables set with your NetSquid username and password.
These are needed for the installation of squidasm.
```
export NETSQUIDPYPI_USER=<username>
export NETSQUIDPYPI_PWD=<password>
```

Install `squidasm`:
```
make install-tests
```

After installation, the simulations can be run.
