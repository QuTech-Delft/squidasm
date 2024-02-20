import unittest
from typing import Dict, List, Tuple

import netsquid as ns
import numpy as np
from netsquid_netbuilder.modules.links.depolarise import DepolariseLinkBuilder, DepolariseLinkConfig
from netsquid_netbuilder.modules.links.heralded_double_click import (
    HeraldedDoubleClickLinkBuilder,
    HeraldedDoubleClickLinkConfig,
)
from netsquid_netbuilder.modules.links.heralded_single_click import (
    HeraldedSingleClickLinkBuilder,
    HeraldedSingleClickLinkConfig,
)
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig
from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_netbuilder.modules.clinks.instant import InstantCLinkConfig
from netsquid_netbuilder.modules.photonic_interface.depolarizing import (
    DepolarizingPhotonicInterfaceBuilder,
    DepolarizingPhotonicInterfaceConfig,
)
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.fidelity import (
    calculate_fidelity_epr,
    fidelity_to_prob_max_mixed,
    prob_max_mixed_to_fidelity,
)
from netsquid_netbuilder.util.network_generation import create_qia_prototype_network
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.util.test_protocol_link import (
    EGPCreateProtocol,
    EGPEventRegistration,
    EGPReceiveProtocol,
)


class TestPhotonicInterfaceChain(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        ns.set_random_state(seed=42)
        np.random.seed(seed=42)

        ns.set_qstate_formalism(ns.QFormalism.DM)

        self.builder = get_test_network_builder()
        self.builder.register_link(
            "depolarise", DepolariseLinkBuilder, DepolariseLinkConfig
        )
        self.builder.register_link(
            "heralded-single-click",
            HeraldedSingleClickLinkBuilder,
            HeraldedSingleClickLinkConfig,
        )
        self.builder.register_link(
            "heralded-double-click",
            HeraldedDoubleClickLinkBuilder,
            HeraldedDoubleClickLinkConfig,
        )
        self.builder.register_photonic_interface(
            "depolarise",
            DepolarizingPhotonicInterfaceBuilder,
            DepolarizingPhotonicInterfaceConfig,
        )

    def tearDown(self) -> None:
        pass


    def _check_fidelity(self, result_register: EGPEventRegistration):
        received_egp_with_full_dm = [
            received_egp
            for received_egp in result_register.received_egp
            if received_egp.dm.shape[0] > 2
        ]
        # The protocol will discard qubits after registering the results, thereby destroying half of the state.
        # The second party to look at the qubit state, will thus see a DM with only one qubit.
        self.assertEqual(
            len(received_egp_with_full_dm), len(result_register.received_egp) / 2
        )

        for received_egp in received_egp_with_full_dm:
            fid = calculate_fidelity_epr(
                received_egp.dm, received_egp.result.bell_state
            )
            self.assertGreater(fid, 0.99)

    def _check_timing(
        self,
        result_register: EGPEventRegistration,
        distance_dict: Dict[Tuple[str, str], List[float]],
    ):
        for received_egp in result_register.received_egp:
            distances = distance_dict[(received_egp.node_name, received_egp.peer_name)]
            distances_new = [distances[0] + distances[1]]
            distances_new += distances[2:-2]
            distances_new += [distances[-2] + distances[-1]]
            expected_time = max(distances_new)
            self.assertAlmostEqual(expected_time, received_egp.time)

    def _perform_epr_test_run(
        self,
        network_cfg: NetworkConfig,
        num_epr: int,
        minimum_fidelity: float = 0,
    ):
        network = self.builder.build(network_cfg)

        protocols = {}
        result_register = EGPEventRegistration()

        sender_name = "sender"
        receiver_name = "receiver"
        sender = EGPCreateProtocol(
            receiver_name, result_register, minimum_fidelity=minimum_fidelity, n_epr=num_epr
        )
        receiver = EGPReceiveProtocol(sender_name, result_register, n_epr=num_epr)

        protocols[sender_name] = sender
        protocols[receiver_name] = receiver

        run(network, protocols)

        received_egp_with_full_dm = [
            received_egp
            for received_egp in result_register.received_egp
            if received_egp.dm.shape[0] > 2
        ]

        fid_list = [calculate_fidelity_epr(r.dm, r.result.bell_state) for r in received_egp_with_full_dm]
        fid = np.average(fid_list)

        times = sorted([r.time for r in received_egp_with_full_dm])
        completion_times = [times[0] - result_register.received_classical[0].time]
        completion_times += [times[i+1] - times[i] for i in range(len(times)-1)]

        completion_time = np.average(completion_times)
        return fid, completion_time

    def _create_network(self, repeater_distances: list, end_distance: float,
                        link_typ: str, link_cfg,
                        photonic_interface_typ: str,
                        photonic_interface_cfg) -> NetworkConfig:
        network_cfg = create_qia_prototype_network(
            nodes_hub1=["sender"],
            node_distances_hub1=[end_distance],
            nodes_hub2=["receiver"],
            node_distances_hub2=[end_distance],
            num_nodes_repeater_chain=len(repeater_distances) - 1,
            node_distances_repeater_chain=repeater_distances,
            link_typ=link_typ,
            link_cfg=link_cfg,
            clink_typ="instant",
            clink_cfg=InstantCLinkConfig(),
            photonic_interface_typ=photonic_interface_typ,
            photonic_interface_cfg=photonic_interface_cfg
        )
        return network_cfg

    def test_photonic_interface_perfect_link_perfect_interface(self):
        repeater_distances = [10, 20, 20, 10]
        end_distance = 10

        link_cfg = PerfectLinkConfig(speed_of_light=1e9)
        photonic_interface_cfg = DepolarizingPhotonicInterfaceConfig(fidelity=1, p_loss=0)
        network_cfg = self._create_network(repeater_distances, end_distance,
                                           link_typ="perfect", link_cfg=link_cfg,
                                           photonic_interface_typ="depolarise",
                                           photonic_interface_cfg=photonic_interface_cfg)

        fid, completion_time = self._perform_epr_test_run(network_cfg, num_epr=1)

        self.assertAlmostEqual(fid, 1, delta=1e-9)
        self.assertAlmostEqual(completion_time, 20, delta=1e-9)

    def test_photonic_interface_perfect_link(self):
        repeater_distances = [10, 20, 20, 10]
        end_distance = 10
        prob_max_mixed_single_interface = 0.3
        prob_loss_single_interface = 0.7

        link_cfg = DepolariseLinkConfig(speed_of_light=1e9, fidelity=1, prob_success=1)
        photonic_interface_cfg = DepolarizingPhotonicInterfaceConfig(prob_max_mixed=prob_max_mixed_single_interface,
                                                                     p_loss=prob_loss_single_interface)

        network_cfg = self._create_network(repeater_distances, end_distance,
                                           link_typ="depolarise", link_cfg=link_cfg,
                                           photonic_interface_typ="depolarise", photonic_interface_cfg=photonic_interface_cfg)

        fid, completion_time = self._perform_epr_test_run(network_cfg, num_epr=100)

        # Find expected fidelity by computing probability that the state is not maximally mixed
        prob_max_mixed = 1 - (1 - prob_max_mixed_single_interface)**2

        # Find the expected completion time
        assert repeater_distances[0] == repeater_distances[-1]
        single_epr_attempt_time = end_distance + repeater_distances[0]
        expected_completion_time = 3/2 * single_epr_attempt_time / (1-prob_loss_single_interface)

        self.assertAlmostEqual(fid, prob_max_mixed_to_fidelity(prob_max_mixed),
                               delta=1e-9)
        self.assertAlmostEqual(completion_time, expected_completion_time,
                               delta=expected_completion_time*0.05)

    def test_photonic_interface(self):
        repeater_distances = [10, 20, 20, 10]
        end_distance = 10
        prob_max_mixed_single_interface = 0.2
        link_fidelity = 0.9
        prob_loss_single_interface = 1 - 0.001
        prob_success_link = 0.1

        link_cfg = DepolariseLinkConfig(speed_of_light=1e9, fidelity=link_fidelity, prob_success=prob_success_link)
        photonic_interface_cfg = DepolarizingPhotonicInterfaceConfig(prob_max_mixed=prob_max_mixed_single_interface,
                                                                     p_loss=prob_loss_single_interface
)

        network_cfg = self._create_network(repeater_distances, end_distance,
                                           link_typ="depolarise", link_cfg=link_cfg,
                                           photonic_interface_typ="depolarise", photonic_interface_cfg=photonic_interface_cfg)

        fid, completion_time = self._perform_epr_test_run(network_cfg, num_epr=100)

        # Find expected fidelity by computing probability that the state is not maximally mixed
        prob_max_mixed_link = fidelity_to_prob_max_mixed(link_fidelity)
        prob_max_mixed = 1 - (1 - prob_max_mixed_single_interface)**2 * (1-prob_max_mixed_link)**4

        # Find the expected completion time, the contribution to the expected completion time from the links without
        # photonic interface is ignored
        assert repeater_distances[0] == repeater_distances[-1]
        single_epr_attempt_time = end_distance + repeater_distances[0]
        expected_completion_time = 3/2 * single_epr_attempt_time / ((1-prob_loss_single_interface) * prob_success_link)

        self.assertAlmostEqual(fid, prob_max_mixed_to_fidelity(prob_max_mixed),
                               delta=1e-9)
        self.assertAlmostEqual(completion_time, expected_completion_time,
                               delta=expected_completion_time*0.05)
