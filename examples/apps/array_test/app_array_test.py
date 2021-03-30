from netqasm.sdk import EPRSocket
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.lang.parsing.text import parse_text_subroutine
from netqasm.backend.messages import SubroutineMessage
from netqasm.lang.instr.flavour import NVFlavour

from qlink_interface import EPRType


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={},
):
    kwargs = {
        "app_name": "client",
        "log_config": None,
        "compiler": NVSubroutineCompiler,
        "return_arrays": True,
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
        num_pairs = 5
        array_len = num_pairs * 10
        init_values = [0 for i in range(array_len)]
        init_values[0] = 1337
        init_values[7] = 42
        init_values[-1] = 777
        outcomes = client.new_array(array_len, init_values=init_values)
        outcomes.get_future_index(0).add(2)

        second_array = client.new_array(20)

    print(list(outcomes))
    print(list(second_array))


if __name__ == "__main__":
    main()
