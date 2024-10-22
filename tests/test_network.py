import os
import tempfile
import unittest
from typing import List

from netqasm.examples.apps.teleport.app_receiver import main as receiver_main
from netqasm.examples.apps.teleport.app_sender import main as sender_main
from netqasm.runtime.application import Application, ApplicationInstance, Program
from netqasm.runtime.env import get_timed_log_dir
from netqasm.runtime.interface.config import (
    Link,
    NetworkConfig,
    Node,
    NoiseType,
    QuantumHardware,
    Qubit,
)
from netqasm.sdk.config import LogConfig

from squidasm.run.multithread.runtime_mgr import SquidAsmRuntimeManager

_DEFAULT_NUM_QUBITS = 5


def get_network_config(
    node_names: List[str],
    hardware: QuantumHardware = QuantumHardware.Generic,
    link_noise_type: NoiseType = NoiseType.NoNoise,
) -> NetworkConfig:
    """Create a config for a fully connected network of nodes with the given names"""
    nodes = []
    links = []
    for name in node_names:
        qubits = [Qubit(id=i, t1=0, t2=0) for i in range(_DEFAULT_NUM_QUBITS)]
        node = Node(name=name, hardware=hardware, qubits=qubits, gate_fidelity=1)
        nodes += [node]

        for other_name in node_names:
            if other_name == name:
                continue
            link = Link(
                name=f"link_{name}_{other_name}",
                node_name1=name,
                node_name2=other_name,
                noise_type=link_noise_type,
                fidelity=1,
            )
            links += [link]

    return NetworkConfig(nodes, links)


class TestNetwork(unittest.TestCase):
    @staticmethod
    def run_network_test(
        hardware: QuantumHardware = QuantumHardware.Generic,
        link_noise_type: NoiseType = NoiseType.NoNoise,
    ):
        with tempfile.TemporaryDirectory() as dirpath:

            mgr = SquidAsmRuntimeManager()
            network_cfg = get_network_config(
                ["delft", "amsterdam"],
                hardware=hardware,
                link_noise_type=link_noise_type,
            )

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

    def test_generic(self):
        self.run_network_test(
            hardware=QuantumHardware.Generic, link_noise_type=NoiseType.NoNoise
        )

    def test_nv(self):
        self.run_network_test(
            hardware=QuantumHardware.NV, link_noise_type=NoiseType.NoNoise
        )

    def test_depolarise(self):
        self.run_network_test(
            hardware=QuantumHardware.Generic, link_noise_type=NoiseType.Depolarise
        )

    def test_discrete_depolarise(self):
        self.run_network_test(
            hardware=QuantumHardware.Generic,
            link_noise_type=NoiseType.DiscreteDepolarise,
        )

    def test_bitflip(self):
        self.run_network_test(
            hardware=QuantumHardware.Generic, link_noise_type=NoiseType.Bitflip
        )
