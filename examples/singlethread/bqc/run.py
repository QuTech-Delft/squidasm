import logging
import time

from netqasm.logging.glob import set_log_level
from netqasm.runtime.interface.config import QuantumHardware, default_network_config
from netqasm.runtime.settings import Simulator, set_simulator

from squidasm.run.singlethread import NetSquidContext, run_files
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.nv_config import nv_cfg_from_file


def main():
    set_log_level(logging.WARNING)
    set_simulator(Simulator.NETSQUID_SINGLE_THREAD)

    network_cfg = default_network_config(
        ["server", "client"], hardware=QuantumHardware.NV
    )  # NOTE the order in which node names are given determines their node IDs
    nv_cfg = nv_cfg_from_file("examples/singlethread/bqc/nv.yaml")
    network = NetSquidNetwork(network_cfg, nv_cfg)

    NetSquidContext.set_nodes({0: "server", 1: "client"})

    client = "./app_client.py"
    server = "./app_server.py"

    start = time.perf_counter()

    num = 20
    results = run_files(
        num=num,
        network=network,
        filenames={"client": client, "server": server},
        insert_yields=True,  # add required `yield from` keywords to source
    )

    print(f"Finished simulation in {round(time.perf_counter() - start, 2)} seconds")

    zeros = len([r for r in results if r[1]["m2"] == 0]) / num
    print("\nOutcome distribution:")
    print(f"0: {round(zeros, 2)}")
    print(f"1: {round(1-zeros, 2)}")


if __name__ == "__main__":
    main()
