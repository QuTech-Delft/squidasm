import logging
import time

from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config

from squidasm.run.singlethread import NetSquidContext, run_files
from squidasm.sim.network.network import NetSquidNetwork


def main():
    set_log_level(logging.WARNING)

    network_cfg = default_network_config(
        ["client", "server"], hardware=QuantumHardware.NV
    )
    network = NetSquidNetwork(network_cfg)

    NetSquidContext.set_nodes({0: "client", 1: "server"})

    client = "examples/apps/bqc_5_5/app_client.py"
    server = "examples/apps/bqc_5_5/app_server.py"

    start = time.perf_counter()

    results = run_files(
        num=10,
        network=network,
        filenames={"client": client, "server": server},
        insert_yields=True,
    )
    print(results)
    m2_0_count = len([r for r in results if r[1]["m2"] == 0])
    print(m2_0_count)

    print(f"finished simulation in {round(time.perf_counter() - start, 2)} seconds")


if __name__ == "__main__":
    main()
