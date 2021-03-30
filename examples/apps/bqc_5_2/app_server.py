from netqasm.sdk import Qubit
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False}, inputs={}):
    socket = Socket("server", "client")

    kwargs = {
        "app_name": "server",
        "log_config": None,
        "compiler": NVSubroutineCompiler,
    }

    # Initialize the connection
    if not app_config["debug"]:
        server = NetQASMConnection(**kwargs, addr=app_config["addr"], port=app_config["port"],
                                   dev=app_config["dev"])
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        server = DebugConnection(**kwargs)

    alpha = float(socket.recv())

    with server:
        electron = Qubit(server)
        carbon = Qubit(server)

        carbon.H()
        electron.H()
        electron.cphase(carbon)

        electron.rot_Z(angle=alpha)
        electron.H()
        m1 = electron.measure(store_array=False)
        m1 = m1 if not app_config["debug"] else 0

        server.flush()

        socket.send(str(m1))

        beta = float(socket.recv())

        carbon.rot_Z(angle=beta)
        carbon.H()
        m2 = carbon.measure(store_array=False)
        m2 = m2 if not app_config["debug"] else 0

    m1, m2 = int(m1), int(m2)
    return {'m1': m1, 'm2': m2}


if __name__ == "__main__":
    main()
