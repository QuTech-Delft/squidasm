import itertools
import unittest
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


@dataclass
class QIANetworkDescription:
    distances_h1: List[float] = field(default_factory=list)
    distances_h2: List[float] = field(default_factory=list)
    repeater_distances: List[float] = field(default_factory=list)
    sender_names: List[str] = field(default_factory=list)
    receiver_names: List[str] = field(default_factory=list)


class TestRepeaterChain(unittest.TestCase):
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

    def tearDown(self) -> None:
        pass

    def _perform_classical_delay_test(
        self,
        network_cfg: StackNetworkConfig,
        sender_names: List[str],
        receiver_names: List[str],
        distances: Dict[Tuple[str, str], List[float]],
    ):
        network = self.builder.build(network_cfg)

        messages = ["test"]
        message_times = [0]
        protocols = {}
        expected_delays = {}
        result_register = ClassicalMessageEventRegistration()
        assert len(sender_names) == len(receiver_names)

        for i, (sender_name, receiver_name) in enumerate(
            zip(sender_names, receiver_names)
        ):
            sender = ClassicalSenderProtocol(
                receiver_name, result_register, messages, message_times
            )
            receiver = ClassicalReceiverProtocol(sender_name, result_register)
            expected_delay = sum(distances[sender_name, receiver_name])

            protocols[sender_name] = sender
            protocols[receiver_name] = receiver

            expected_delays[sender_name] = expected_delay
            expected_delays[receiver_name] = expected_delay

        run(network, protocols)

        for classical_message_info in result_register.received:
            self.assertEqual(classical_message_info.msg, messages[0])
            self.assertAlmostEqual(
                classical_message_info.time,
                expected_delays[classical_message_info.peer],
                delta=1e-9,
            )

    @staticmethod
    def _calculate_distances(network: QIANetworkDescription):
        distances_dict = {}
        for idx_h1, idx_h2 in itertools.product(
            range(len(network.sender_names)), range(len(network.receiver_names))
        ):
            distances_dict[
                (network.sender_names[idx_h1], network.receiver_names[idx_h2])
            ] = (
                [network.distances_h1[idx_h1]]
                + network.repeater_distances
                + [network.distances_h2[idx_h2]]
            )
            distances_dict[
                (network.receiver_names[idx_h2], network.sender_names[idx_h1])
            ] = distances_dict[
                (network.sender_names[idx_h1], network.receiver_names[idx_h2])
            ]

        return distances_dict

    def test_classical_delay(self):
        num_end_nodes = 6
        network = QIANetworkDescription()
        network.distances_h1 = [12, 53, 38]
        network.distances_h2 = [81, 1, 8]
        network.repeater_distances = [213, 2, 51, 89]
        network.sender_names = [f"sender_{i}" for i in range(num_end_nodes // 2)]
        network.receiver_names = [f"receiver_{i}" for i in range(num_end_nodes // 2)]

        network_cfg = create_qia_prototype_network(
            nodes_hub1=network.sender_names,
            node_distances_hub1=network.distances_h1,
            nodes_hub2=network.receiver_names,
            node_distances_hub2=network.distances_h2,
            num_nodes_repeater_chain=len(network.repeater_distances) - 1,
            node_distances_repeater_chain=network.repeater_distances,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=1e9),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
        )

        distances_dict = self._calculate_distances(network)

        self._perform_classical_delay_test(
            network_cfg, network.sender_names, network.receiver_names, distances_dict
        )

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
        sender_names: List[str],
        receiver_names: List[str],
        minimum_fidelity: float = 0,
    ):
        network = self.builder.build(network_cfg)

        protocols = {}
        result_register = EGPEventRegistration()
        assert len(sender_names) == len(receiver_names)

        # TODO the repeater chain can't handle multiple simultaneous requests
        sender_name = sender_names[0]
        receiver_name = receiver_names[0]
        sender = EGPCreateProtocol(
            receiver_name, result_register, minimum_fidelity=minimum_fidelity
        )
        receiver = EGPReceiveProtocol(sender_name, result_register)

        protocols[sender_name] = sender
        protocols[receiver_name] = receiver

        run(network, protocols)

        return result_register

    def _check_delays(
        self, result_register: EGPEventRegistration, distances: Dict[str, float]
    ):
        for received_egp in result_register.received_egp:
            dist1 = distances[received_egp.node_name]
            dist2 = distances[received_egp.peer_name]

            single_com_time = dist1 + dist2
            classical_handshake = single_com_time
            epr_round_time = single_com_time
            expected_delay = classical_handshake + epr_round_time

            self.assertAlmostEqual(expected_delay, received_egp.time, delta=1e-9)

    def test_repeater_perfect_delay(self):
        num_end_nodes = 6
        network = QIANetworkDescription()
        network.distances_h1 = [12, 53, 38]
        network.distances_h2 = [81, 1, 8]
        network.repeater_distances = [213, 2, 51, 89]
        network.sender_names = [f"sender_{i}" for i in range(num_end_nodes // 2)]
        network.receiver_names = [f"receiver_{i}" for i in range(num_end_nodes // 2)]

        network_cfg = create_qia_prototype_network(
            nodes_hub1=network.sender_names,
            node_distances_hub1=network.distances_h1,
            nodes_hub2=network.receiver_names,
            node_distances_hub2=network.distances_h2,
            num_nodes_repeater_chain=len(network.repeater_distances) - 1,
            node_distances_repeater_chain=network.repeater_distances,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=1e9),
            clink_typ="instant",
            clink_cfg=InstantCLinkConfig(),
        )

        result_register = self._perform_epr_test_run(
            network_cfg, network.sender_names, network.receiver_names
        )

        distances_dict = self._calculate_distances(network)

        self._check_fidelity(result_register)
        self._check_timing(result_register, distances_dict)
