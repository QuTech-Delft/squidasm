from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={},
):

    socket = Socket("server", "client")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("client", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "server",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
    }

    # Initialize the connection
    if not app_config["debug"]:
        server = NetQASMConnection(
            **kwargs,
            addr=app_config["addr"],
            port=app_config["port"],
            dev=app_config["dev"]
        )
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        server = DebugConnection(**kwargs)

    with server:
        epr = epr_socket.recv()[0]

        q = Qubit(server)
        q.H()

        epr.cphase(q)

        server.flush()

        delta1 = float(socket.recv())

        epr.rot_Z(angle=delta1)
        epr.H()
        m1 = epr.measure(store_array=False)
        m1 = m1 if not app_config["debug"] else 0
        server.flush()

        socket.send(str(m1))

        delta2 = float(socket.recv())

        q.rot_Z(angle=delta2)
        q.H()
        m2 = q.measure(store_array=False)
        m2 = m2 if not app_config["debug"] else 0
        server.flush()

    m1, m2 = int(m1), int(m2)
    return {"m1": m1, "m2": m2}


if __name__ == "__main__":
    main()
