import unittest

import netsquid as ns
from netqasm.backend.messages import InitNewAppMessage, OpenEPRSocketMessage

from squidasm.run.stack.build import build_nv_qdevice
from squidasm.run.stack.config import NVQDeviceConfig
from squidasm.sim.stack.handler import Handler
from squidasm.sim.stack.netstack import EprSocket, Netstack
from squidasm.sim.stack.stack import NodeStack


class TestHandler(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        qdevice = build_nv_qdevice("nv_qdevice_alice", cfg=NVQDeviceConfig())
        self._node = NodeStack("alice", qdevice_type="nv", qdevice=qdevice)

    @property
    def handler(self) -> Handler:
        return self._node.qnos.handler

    @property
    def netstack(self) -> Netstack:
        return self._node.qnos.netstack

    def tearDown(self) -> None:
        pass

    def test_register_app(self):
        self.handler.msg_from_host(InitNewAppMessage(0, 2))
        assert 0 in self.handler._applications

    def test_open_epr_socket(self):
        self.handler.msg_from_host(OpenEPRSocketMessage(0, 2, 1))
        assert 0 in self.netstack._epr_sockets
        assert self.netstack._epr_sockets[0][0] == EprSocket(2, 1)


if __name__ == "__main__":
    unittest.main()
