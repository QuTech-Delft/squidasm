import os
import tempfile

from netqasm.examples.apps.teleport.app_receiver import main as receiver_main
from netqasm.examples.apps.teleport.app_sender import main as sender_main
from netqasm.runtime.application import Application, ApplicationInstance, Program
from netqasm.runtime.env import get_timed_log_dir
from netqasm.runtime.interface.config import default_network_config
from netqasm.sdk.config import LogConfig
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.qubit import Qubit

from squidasm.run.multithread.runtime_mgr import SquidAsmRuntimeManager


def alice_entry():
    alice = NetQASMConnection(app_name="alice")
    with alice:
        q = Qubit(alice)
        q.H()
        q.measure()
    pass


def bob_entry():
    pass


def test():
    with tempfile.TemporaryDirectory() as dirpath:

        mgr = SquidAsmRuntimeManager()
        network_cfg = default_network_config(["delft", "amsterdam"])

        prog_sender = Program(
            party="sender", entry=sender_main, args=["app_config"], results=[]
        )
        prog_receiver = Program(
            party="receiver", entry=receiver_main, args=["app_config"], results=[]
        )

        log_cfg = LogConfig(
            track_lines=False, log_subroutines_dir=dirpath, comm_log_dir=dirpath
        )

        app = Application(programs=[prog_sender, prog_receiver], metadata=None)
        app_instance = ApplicationInstance(
            app=app,
            program_inputs={
                "sender": {},
                "receiver": {},
            },
            network=None,
            party_alloc={
                "sender": "delft",
                "receiver": "amsterdam",
            },
            logging_cfg=log_cfg,
        )

        mgr.set_network(network_cfg)
        backend_log_dir = os.path.join(dirpath, "backend_log")
        if not os.path.exists(backend_log_dir):
            os.mkdir(backend_log_dir)
        mgr.backend_log_dir = backend_log_dir
        mgr.start_backend()
        for i in range(1):
            print(f"\niteration {i}")
            if app_instance.logging_cfg is not None:
                log_dir = get_timed_log_dir(dirpath)
                app_instance.logging_cfg.log_subroutines_dir = log_dir
                app_instance.logging_cfg.comm_log_dir = log_dir
            results = mgr.run_app(app_instance)
            print(f"results: {results}")
        mgr.stop_backend()


if __name__ == "__main__":
    test()
