from netqasm.sdk import EPRSocket
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.compiling import NVSubroutineCompiler

from qlink_interface import EPRType


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={'num_pairs': 10, 'basis': 'Z'},
):
    num_pairs = inputs['num_pairs']
    basis = inputs['basis']
    assert basis in ['X', 'Y', 'Z']

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
        outcomes = client.new_array(num_pairs)

        def post_create(conn, q, pair):
            array_entry = outcomes.get_future_index(pair)
            if basis == 'X':
                q.H()
            elif basis == 'Y':
                q.K()
            # store measurement outcome in array
            q.measure(array_entry)

        # Create EPR pair
        epr_socket.create(
            number=num_pairs,
            tp=EPRType.K,
            sequential=True,
            post_routine=post_create,
        )

    if app_config["debug"]:
        # For some reason iterating (`for outcome in outcomes`) is really slow
        bits = [0 for i in range(len(outcomes))]
    else:
        bits = [int(b) for b in outcomes]
    print("".join(str(b) for b in bits))
    return bits


if __name__ == "__main__":
    main()
