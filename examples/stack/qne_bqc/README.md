
## Prerequisites
To run the code, a specific version of the `netqasm` and `squidasm` packages are needed.
`squidasm` relies on [NetSquid](https://netsquid.org/).
To install NetSquid, an account is needed. See the NetSquid website how this is done.

### Installation
First install `netqasm` version 0.9.1:

```
pip install netqasm==0.9.1
```

Then, clone the squidasm repostitory and checkout the `qne-hardware` branch:
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
make install
```

After installation, the simulations can be run as described below.

## BQC application

We consider a simple BQC application consisting of a client and a server.
A server performs an Effective Computation (EC) on behalf of the client.

In the so-called *computation rounds*, the client makes the server perform the EC.
In the *trap rounds*, the client sends dummy information to the server just to check
if the server is behaving honestly.

### Effective Computation (EC)
Effective Computation (**EC**): `H Rz[beta] H Rz[alpha] |+>` followed by a measurement in the Z-basis. 
(Exact prepared state: `Z^(m1) H Rz[beta] H Rz[alpha] |+>` )
![](fig/5_6_effective.png)

### EC implementation using Remote State Preparation and Measurement Based Quantum Computation
The following circuit produces equivalent results to the EC.
It is a 'blind version' of the EC.
![](fig/5_6_generic.png)

Blue values are sent from server to client.
Red values are computed by the client and sent to the server.

### Inputs
- `alpha`: parameter of EC
- `beta`: parameter of EC
- `theta1`: randomly chosen by client from `[0, pi/4, ..., 7pi/4]`. Does not affect the EC.
- `theta2`: randomly chosen by client from `[0, pi/4, ..., 7pi/4]`. Does not affect the EC.

### Expected measurement outcomes
- `p1`: uniformly random
- `p2`: uniformly random
- `m1`: uniformly random
- `m2`: outcome of **EC**. Expected statistics depend on alpha and beta.


## Simulation scripts
Examples of simulation code are in the `examples/stack` directory. The `examples/stack/qne_bqc` directory in there can be used to do simulations for the QNE parameter estimation.
It contains BQC application code file and some configuration files. `example_bqc_nv.py` is the full BQC application, including trap rounds and
computation of the error rate. Simply running the file with

```
python examples/stack/qne_bqc/example_bqc_nv.py
```
will run the simulation. The data it produces is simply printed or ignored.
One can simply add code to e.g. store the data to a file or to create plots from them.

The `config_nv.yaml` file contains configuration parameters for the hardware of the nodes and the entanglement link.
Check https://docs.netsquid.org/snippets/netsquid-nv/modules/magic_distributor.html#netsquid_nv.magic_distributor.NVSingleClickMagicDistributor for information about the link parameters, and the comments in the `config_nv.yaml` file itself for the node parameters.