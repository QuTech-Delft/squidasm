import math

from netqasm.sdk import EPRSocket
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection, Socket


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={
        "alpha": math.pi / 2,
        "beta": math.pi / 2,
        "theta1": 0,
        "theta2": 0,
        "r1": 0,
        "r2": 0,
        "trap": False,
        "dummy": 0,
    },
):
    alpha, beta, theta1, theta2, r1, r2 = (
        inputs["alpha"],
        inputs["beta"],
        inputs["theta1"],
        inputs["theta2"],
        inputs["r1"],
        inputs["r2"],
    )

    # Whether it is a trap round or not
    trap = inputs["trap"]

    if trap:
        dummy = inputs["dummy"]

    socket = Socket("client", "server")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("server", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "client",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
    }

    # Initialize the connection
    if not app_config["debug"]:
        client = NetQASMConnection(
            **kwargs,
            addr=app_config["addr"],
            port=app_config["port"],
            dev=app_config["dev"]
        )
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        client = DebugConnection(**kwargs)

    with client:
        # Create EPR pair
        epr1 = epr_socket.create()[0]

        # RSP
        if trap and dummy == 2:
            # remotely-prepare a dummy state
            p2 = epr1.measure(store_array=False)
        else:
            epr1.rot_Z(angle=theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)
        p2 = p2 if not app_config["debug"] else 0

        # Create EPR pair
        epr2 = epr_socket.create()[0]

        # RSP
        if trap and dummy == 1:
            # remotely-prepare a dummy state
            p1 = epr2.measure(store_array=False)
        else:
            epr2.rot_Z(angle=theta1)
            epr2.H()
            p1 = epr2.measure(store_array=False)
        p1 = p1 if not app_config["debug"] else 0
        client.flush()

        p1 = int(p1)
        p2 = int(p2)

        if trap and dummy == 2:
            delta1 = -theta1 + (p1 + r1) * math.pi
        else:
            delta1 = alpha - theta1 + (p1 + r1) * math.pi
        socket.send(str(delta1))

        m1 = int(socket.recv())
        if trap and dummy == 1:
            delta2 = -theta2 + (p2 + r2) * math.pi
        else:
            delta2 = math.pow(-1, (m1 + r1)) * beta - theta2 + (p2 + r2) * math.pi
        socket.send(str(delta2))

    return {"p1": p1, "p2": p2}


if __name__ == "__main__":
    main()
