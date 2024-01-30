import itertools
import unittest

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import netsquid as ns
from netsquid_magic.models.depolarise import DepolariseLinkBuilder, DepolariseLinkConfig
from netsquid_magic.models.heralded_double_click import (
    HeraldedDoubleClickLinkBuilder,
    HeraldedDoubleClickLinkConfig,
)
from netsquid_magic.models.heralded_single_click import (
    HeraldedSingleClickLinkBuilder,
    HeraldedSingleClickLinkConfig,
)
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.clinks.instant import InstantCLinkConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.fidelity import calculate_fidelity_epr
from netsquid_netbuilder.util.network_generation import create_qia_prototype_network
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.modules.photonic_interface.depolarizing import DepolarizingPhotonicInterfaceConfig, DepolarizingPhotonicInterfaceBuilder
from netsquid_netbuilder.util.test_protocol_clink import (
    ClassicalMessageEventRegistration,
    ClassicalReceiverProtocol,
    ClassicalSenderProtocol,
)
from netsquid_netbuilder.util.test_protocol_link import (
    EGPCreateProtocol,
    EGPEventRegistration,
    EGPReceiveProtocol,
)


class TestPhotonicInterfaceChain(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
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
        network_cfg: StackNetworkConfig,
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

        completion_time = np.average([r.time for r in result_register.received_egp])

        return fid, completion_time

    def _create_network(self, repeater_distances: list, end_distance: float,
                        link_typ: str, link_cfg,
                        photonic_interface_typ: str,
                        photonic_interface_cfg) -> StackNetworkConfig:
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

    def test_photonic_interface_fidelity_perfect(self):
        repeater_distances = [10, 10, 10, 10]
        end_distance = 10

        link_cfg = PerfectLinkConfig(speed_of_light=1e9)
        photonic_interface_cfg = DepolarizingPhotonicInterfaceConfig(prob_max_mixed=0.1, p_loss=0)

        network_cfg = self._create_network(repeater_distances, end_distance,
                                           link_typ="perfect", link_cfg=link_cfg,
                                           photonic_interface_typ="depolarise", photonic_interface_cfg=photonic_interface_cfg)

        fid, completion_time = self._perform_epr_test_run(network_cfg, num_epr=100)

        print(fid, completion_time)

    def test_photonic_interface_fidelity(self):
        repeater_distances = [10, 10, 10, 10]
        end_distance = 10

        link_cfg = DepolariseLinkConfig(speed_of_light=1e9, fidelity=0.9, prob_success=1)
        photonic_interface_cfg = DepolarizingPhotonicInterfaceConfig(prob_max_mixed=0, p_loss=0)

        network_cfg = self._create_network(repeater_distances, end_distance,
                                           link_typ="depolarise", link_cfg=link_cfg,
                                           photonic_interface_typ=None, photonic_interface_cfg=None)

        fid, completion_time = self._perform_epr_test_run(network_cfg, num_epr=100)

        print(fid, completion_time)
