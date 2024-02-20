import unittest
import netsquid as ns
import numpy as np
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.util.network_generation import create_2_node_network
from netsquid_netbuilder.util.test_protocol_link import EGPCreateProtocol, EGPReceiveProtocol, EGPEventRegistration
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig, PerfectLinkBuilder
from netsquid_netbuilder.modules.links.depolarise import DepolariseLinkConfig, DepolariseLinkBuilder
from netsquid_netbuilder.run import run
from netsquid.qubits.ketstates import BellIndex
from netsquid_netbuilder.util.fidelity import calculate_fidelity_epr

from qlink_interface import ResCreateAndKeep


class TestPerfectLinkModel(unittest.TestCase):
    def setUp(self):
        self.builder = get_test_network_builder()
        ns.set_qstate_formalism(ns.QFormalism.DM)

    def tearDown(self):
        pass

    def test_1(self):
        delay = 5325.73

        link_cfg = PerfectLinkConfig(state_delay=delay)
        network_cfg = create_2_node_network(link_typ="perfect", link_cfg=link_cfg)
        results_reg = EGPEventRegistration()
        n_epr = 50

        alice_program = EGPCreateProtocol("Bob", results_reg, n_epr)
        bob_program = EGPReceiveProtocol("Alice", results_reg, n_epr)

        network = self.builder.build(network_cfg)
        run(network, {"Alice": alice_program, "Bob": bob_program})

        self.assertEqual(len(results_reg.received_classical), 1)
        self.assertEqual(len(results_reg.received_egp), n_epr * 2)

        res_clas = results_reg.received_classical[0]


        for i in range(n_epr):
            res_egp_1 = results_reg.received_egp[i * 2]
            res_egp_2 = results_reg.received_egp[i * 2 + 1]

            self.assertEqual(res_egp_1.time, res_egp_2.time)
            self.assertAlmostEqual(res_clas.time + delay * (i+1), res_egp_1.time, delta=delay*0.0001)

            res_create_keep: ResCreateAndKeep = res_egp_1.result
            self.assertEqual(res_create_keep.bell_state, BellIndex.B00)

            fid = calculate_fidelity_epr(res_egp_1.dm, res_create_keep.bell_state)
            self.assertGreater(fid, 0.9999)


class TestDepolariseLinkModel(unittest.TestCase):
    def setUp(self):
        ns.set_qstate_formalism(ns.QFormalism.DM)
        self.builder = get_test_network_builder()
        self.builder.register_link("depolarise", DepolariseLinkBuilder, DepolariseLinkConfig)

    def tearDown(self):
        pass

    def test_perfect(self):
        t_cycle = 3246.34

        link_cfg = DepolariseLinkConfig(fidelity=1.0, prob_success=1, t_cycle=t_cycle)
        network_cfg = create_2_node_network(link_typ="depolarise", link_cfg=link_cfg)
        results_reg = EGPEventRegistration()
        n_epr = 50

        alice_program = EGPCreateProtocol("Bob", results_reg, n_epr)
        bob_program = EGPReceiveProtocol("Alice", results_reg, n_epr)

        network = self.builder.build(network_cfg)
        run(network, {"Alice": alice_program, "Bob": bob_program})

        self.assertEqual(len(results_reg.received_classical), 1)
        self.assertEqual(len(results_reg.received_egp), n_epr * 2)

        res_clas = results_reg.received_classical[0]

        for i in range(n_epr):
            res_egp_1 = results_reg.received_egp[i * 2]
            res_egp_2 = results_reg.received_egp[i * 2 + 1]

            self.assertEqual(res_egp_1.time, res_egp_2.time)
            self.assertAlmostEqual(res_clas.time + t_cycle * (i+1), res_egp_1.time, delta=t_cycle*0.0001)

            res_create_keep: ResCreateAndKeep = res_egp_1.result
            self.assertEqual(res_create_keep.bell_state, BellIndex.B00)

            fid = calculate_fidelity_epr(res_egp_1.dm, res_create_keep.bell_state)
            self.assertGreater(fid, 0.9999)

    def test_fidelity(self):
        t_cycle = 3246.34
        for fidelity in np.arange(0, 1, 0.1):

            link_cfg = DepolariseLinkConfig(fidelity=fidelity, prob_success=1, t_cycle=t_cycle)
            network_cfg = create_2_node_network(link_typ="depolarise", link_cfg=link_cfg)
            results_reg = EGPEventRegistration()
            n_epr = 1

            alice_program = EGPCreateProtocol("Bob", results_reg, n_epr)
            bob_program = EGPReceiveProtocol("Alice", results_reg, n_epr)

            network = self.builder.build(network_cfg)
            run(network, {"Alice": alice_program, "Bob": bob_program})

            self.assertEqual(len(results_reg.received_classical), 1)
            self.assertEqual(len(results_reg.received_egp), n_epr * 2)

            res_clas = results_reg.received_classical[0]
            res_egp_1 = results_reg.received_egp[0]
            res_egp_2 = results_reg.received_egp[1]

            self.assertEqual(res_egp_1.time, res_egp_2.time)
            self.assertAlmostEqual(res_clas.time + t_cycle, res_egp_1.time, delta=t_cycle*0.0001)

            res_create_keep: ResCreateAndKeep = res_egp_1.result
            self.assertEqual(res_create_keep.bell_state, BellIndex.B00)

            fid = calculate_fidelity_epr(res_egp_1.dm, res_create_keep.bell_state)

            self.assertAlmostEqual(fid, fidelity, delta=0.1)
