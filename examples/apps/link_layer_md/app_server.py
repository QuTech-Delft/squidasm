from netqasm.sdk.epr_socket import EPRSocket, EPRType
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={'num_pairs': 10},
):
    num_pairs = inputs['num_pairs']

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("client", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "server",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": True,
    }

    # Initialize the connection
    if not app_config["debug"]:
        server = NetQASMConnection(**kwargs, addr=app_config["addr"], port=app_config["port"],
                                   dev=app_config["dev"])
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        server = DebugConnection(**kwargs)

    with server:
        outcomes = epr_socket.recv(number=num_pairs, tp=EPRType.M)

    bits = [int(outcome.measurement_outcome)
            if not app_config["debug"] else 0 for outcome in outcomes]
    print("".join(str(b) for b in bits))
    return bits


if __name__ == "__main__":
    main()
