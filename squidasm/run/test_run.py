import pydynaa
import netsquid as ns
import os
from time import perf_counter

from squidasm.run.runtime_mgr import SquidAsmRuntimeManager
from squidasm.run.runtime_mgr import Program, Application, ApplicationInstance
from netqasm.runtime.interface.config import NetworkConfig, default_network_config

from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.qubit import Qubit

from netqasm.examples.apps.teleport.app_sender import main as sender_main
from netqasm.examples.apps.teleport.app_receiver import main as receiver_main

from netqasm.runtime.app_config import AppConfig
from netqasm.sdk.config import LogConfig

from netqasm.logging.glob import set_log_level


def alice_entry():
    alice = NetQASMConnection(app_name="alice")
    with alice:
        q = Qubit(alice)
        q.H()
        m = q.measure()
    pass


def bob_entry():
    pass


def main():
    mgr = SquidAsmRuntimeManager()
    # network_cfg = default_network_config(["alice", "bob"])
    network_cfg = default_network_config(["delft", "amsterdam"])

    # prog_alice = Program(party="alice", entry=alice_entry, args=[], results=[])
    # prog_bob = Program(party="bob", entry=bob_entry, args=[], results=[])

    prog_sender = Program(party="sender", entry=sender_main, args=["app_config"], results=[])
    prog_receiver = Program(party="receiver", entry=receiver_main, args=["app_config"], results=[])

    log_cfg = LogConfig(track_lines=False, log_subroutines_dir=os.getcwd(), comm_log_dir="TEMP_LOG")
    sender_app_cfg = AppConfig(app_name="sender", node_name="", main_func=None, log_config=log_cfg, inputs=None)
    receiver_app_cfg = AppConfig(app_name="receiver", node_name="", main_func=None, log_config=log_cfg, inputs=None)

    # app = Application(programs=[prog_alice, prog_bob], metadata=None)
    app = Application(programs=[prog_sender, prog_receiver], metadata=None)
    app_instance = ApplicationInstance(
        app=app,
        program_inputs={
            "sender": {"app_config": sender_app_cfg},
            "receiver": {"app_config": receiver_app_cfg},
        },
        network=None,
        party_alloc={
            "sender": "delft",
            "receiver": "amsterdam",
        },
        logging_cfg=None
    )

    mgr.set_network(network_cfg)
    mgr.start_backend()
    for i in range(3):
        print(f"\niteration {i}")
        mgr.run_app(app_instance)
    mgr.stop_backend()

    # mgr.reset_backend()

    mgr.set_network(network_cfg)
    mgr.start_backend()
    mgr.run_app(app_instance)
    mgr.stop_backend()

    # mgr.reset_backend()

    # network_cfg_2 = default_network_config(["alice", "charlie"])
    # mgr.set_network(network_cfg_2)
    # app_instance.party_alloc = {
    #     "alice": "alice",
    #     "bob": "charlie"
    # }
    # mgr.start_backend()
    # mgr.run_app(app_instance)
    # mgr.stop_backend()


if __name__ == "__main__":
    # set_log_level("INFO")
    set_log_level("WARNING")
    start = perf_counter()
    main()
    end = perf_counter()
    print(f"finished in {end - start}")
