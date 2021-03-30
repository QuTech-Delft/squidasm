from netqasm.sdk.epr_socket import EPRSocket, EPRType, EPRMeasBasis
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={'num_pairs': 10, 'basis': 'Z'},
):
    num_pairs = inputs['num_pairs']

    if inputs['basis'] == 'X':
        basis = EPRMeasBasis.X
    elif inputs['basis'] == 'Y':
        basis = EPRMeasBasis.Y
    elif inputs['basis'] == 'Z':
        basis = EPRMeasBasis.Z
    else:
        raise ValueError(f"Invalid basis {inputs['basis']}")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("server", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "client",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": True,
    }

    # Initialize the connection
    if not app_config["debug"]:
        client = NetQASMConnection(**kwargs, addr=app_config["addr"], port=app_config["port"],
                                   dev=app_config["dev"])
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        client = DebugConnection(**kwargs)

    with client:
        outcomes = epr_socket.create(
            number=num_pairs, tp=EPRType.M,
            basis_local=basis, basis_remote=basis)

    bits = [int(outcome.measurement_outcome)
            if not app_config["debug"] else 0 for outcome in outcomes]
    print("".join(str(b) for b in bits))
    return bits


if __name__ == "__main__":
    main()
