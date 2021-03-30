from netqasm.sdk import EPRSocket
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False}, inputs={}):

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("client", min_fidelity=75)

    # Arguments to connection class
    kwargs = {
        "app_name": "server",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
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
        epr = epr_socket.recv()[0]

        epr.H()
        m2 = epr.measure(store_array=False)
        m2 = m2 if not app_config["debug"] else 0
        server.flush()

    m2 = int(m2)
    return {'m2': m2}


if __name__ == "__main__":
    main()
