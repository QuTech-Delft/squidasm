from netqasm.sdk import Qubit
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={'alpha': 0, 'beta': 0}
):
    alpha, beta = inputs['alpha'], inputs['beta']

    # Arguments to connection class
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

    with server:
        electron = Qubit(server)
        carbon = Qubit(server)

        carbon.H()
        electron.H()
        electron.cphase(carbon)

        electron.rot_Z(angle=alpha)
        electron.H()
        m1 = electron.measure(store_array=False)

        with m1.if_eq(1):
            carbon.X()

        m1 = m1 if not app_config["debug"] else 0

        carbon.rot_Z(angle=beta)
        carbon.H()
        m2 = carbon.measure(store_array=False)
        m2 = m2 if not app_config["debug"] else 0

    m1, m2 = int(m1), int(m2)
    return {'m1': m1, 'm2': m2}


if __name__ == "__main__":
    main()
