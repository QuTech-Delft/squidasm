import unittest

import netsquid as ns
from netqasm.sdk import Qubit
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig
from netsquid_netbuilder.modules.qlinks.depolarise import DepolariseQLinkConfig
from netsquid_netbuilder.util.network_generation import create_2_node_network

from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util.routines import teleport_recv, teleport_send


class TeleportSenderProgram(Program):
    def __init__(self, peer_name: str):
        self.peer_name = peer_name
        self.complete = False

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="sender_program",
            csockets=[self.peer_name],
            epr_sockets=[self.peer_name],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        q = Qubit(context.connection)
        yield from teleport_send(q, context, peer_name=self.peer_name)
        self.complete = True


class TeleportReceiverProgram(Program):
    def __init__(self, peer_name: str):
        self.peer_name = peer_name
        self.complete = False

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="receiver_program",
            csockets=[self.peer_name],
            epr_sockets=[self.peer_name],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        yield from teleport_recv(context, peer_name=self.peer_name)
        self.complete = True


class TestRun(unittest.TestCase):
    def test_run(self):
        t_cycle = 100

        network_cfg = create_2_node_network(
            qlink_typ="depolarise",
            qlink_cfg=DepolariseQLinkConfig(
                fidelity=1, prob_success=1, t_cycle=t_cycle
            ),
            qdevice_typ="generic",
            qdevice_cfg=GenericQDeviceConfig.perfect_config(),
        )
        send_prot = TeleportSenderProgram(peer_name="Bob")
        recv_prot = TeleportReceiverProgram(peer_name="Alice")

        run(network_cfg, programs={"Alice": send_prot, "Bob": recv_prot})

        assert send_prot.complete
        assert recv_prot.complete
        self.assertAlmostEqual(ns.sim_time(), t_cycle, delta=t_cycle * 0.01)

    def test_run_twice(self) -> None:
        t_cycle = 100

        network_cfg = create_2_node_network(
            qlink_typ="depolarise",
            qlink_cfg=DepolariseQLinkConfig(
                fidelity=1, prob_success=1, t_cycle=t_cycle
            ),
            qdevice_typ="generic",
            qdevice_cfg=GenericQDeviceConfig.perfect_config(),
        )
        send_prot = TeleportSenderProgram(peer_name="Bob")
        recv_prot = TeleportReceiverProgram(peer_name="Alice")

        run(network_cfg, programs={"Alice": send_prot, "Bob": recv_prot})

        self.assertAlmostEqual(ns.sim_time(), t_cycle, delta=t_cycle * 0.01)
        assert send_prot.complete
        assert recv_prot.complete
        send_prot.complete = False
        recv_prot.complete = False

        run(network_cfg, programs={"Alice": send_prot, "Bob": recv_prot})

        self.assertAlmostEqual(ns.sim_time(), t_cycle, delta=t_cycle * 0.01)
        assert send_prot.complete
        assert recv_prot.complete


if __name__ == "__main__":
    unittest.main()
