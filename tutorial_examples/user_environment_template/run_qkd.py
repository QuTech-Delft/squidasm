import os

from netsquid_netbuilder.base_configs import StackNetworkConfig
from squidasm.run.stack.run import run
from tutorial_examples.user_environment_template.applications.qkd import QkdProgram

if __name__ == "__main__":
    num_times = 2

    cfg = StackNetworkConfig.from_file(
        os.path.join(os.getcwd(), os.path.dirname(__file__),
                     "network_configuration/config_nv.yaml")
    )

    num_bits = 100

    client_program = QkdProgram(num_bits=num_bits, is_client=True)
    server_program = QkdProgram(num_bits=num_bits, is_client=False)

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    for i, (client_result, server_result) in enumerate(zip(client_results, server_results)):
        print(f"run {i}:")
        rk_client = "".join(str(b) for b in client_result["raw_key"])
        rk_server = "".join(str(b) for b in server_result["raw_key"])
        print(f"client raw key: {rk_client}")
        print(f"server raw key: {rk_server}")
        print(f"client error rate: {client_result['error_rate']}")
        print(f"server error rate: {server_result['error_rate']}")