import pathlib
import unittest
from typing import Dict, List

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
from netsquid_netbuilder.modules.scheduler.fifo import FIFOScheduleConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.fidelity import calculate_fidelity_epr
from netsquid_netbuilder.util.network_generation import create_metro_hub_network
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


class TestMetropolitanHub(unittest.TestCase):
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
        distances: List[float],
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
            expected_delay = distances[i] + distances[i + len(sender_names)]

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

    def test_classical_delay(self):
        num_nodes = 6
        distances = [12, 53, 38, 81, 1, 8]
        sender_names = [f"sender_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        network_cfg = create_metro_hub_network(
            node_names=sender_names + receiver_names,
            node_distances=distances,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
        )

        self._perform_classical_delay_test(
            network_cfg, sender_names, receiver_names, distances
        )

    def test_classical_delay_yaml(self):
        num_nodes = 6
        distances = [10.4, 23, 1, 4, 213.3e8, 15]
        sender_names = [f"sender_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        test_dir = pathlib.Path(__file__).parent.resolve()
        network_cfg = StackNetworkConfig.from_file(
            f"{test_dir}/yaml_configs/metro_hub.yaml"
        )

        self._perform_classical_delay_test(
            network_cfg, sender_names, receiver_names, distances
        )

    def test_egp_perfect(self):
        num_nodes = 6
        distances = [5, 9, 32, 23, 213.3e8, 15]
        sender_names = [f"creator_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        network_cfg = create_metro_hub_network(
            node_names=sender_names + receiver_names,
            node_distances=distances,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=1e9),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=0, max_multiplexing=3),
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names
        )
        self._check_delays(result_register, distance_dict)
        self._check_fidelity(result_register)

    def test_egp_depolarizing(self):
        num_nodes = 6
        distances = [10.4, 23, 1, 4, 213.3e8, 15]
        sender_names = [f"creator_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        network_cfg = create_metro_hub_network(
            node_names=sender_names + receiver_names,
            node_distances=distances,
            link_typ="depolarise",
            link_cfg=DepolariseLinkConfig(
                fidelity=1.0, prob_success=1, speed_of_light=1e9
            ),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=0, max_multiplexing=3),
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names
        )
        self._check_delays(result_register, distance_dict)
        self._check_fidelity(result_register)

    def test_egp_depolarizing_yaml(self):
        num_nodes = 6
        distances = [10.4, 23, 1, 4, 213.3e8, 15]
        sender_names = [f"sender_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        test_dir = pathlib.Path(__file__).parent.resolve()
        network_cfg = StackNetworkConfig.from_file(
            f"{test_dir}/yaml_configs/metro_hub_depolarise.yaml"
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names
        )
        self._check_delays(result_register, distance_dict)
        self._check_fidelity(result_register)

    def test_egp_heralded_single_click(self):
        num_nodes = 6
        distances = [100, 23, 1e6, 1e3, 213.3e5, 15e6]
        sender_names = [f"creator_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        link_cfg = HeraldedSingleClickLinkConfig(
            p_loss_init=0,
            p_loss_length=0,
            speed_of_light=1e9,
            emission_fidelity=1,
        )

        network_cfg = create_metro_hub_network(
            node_names=sender_names + receiver_names,
            node_distances=distances,
            link_typ="heralded-single-click",
            link_cfg=link_cfg,
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=0, max_multiplexing=3),
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0
        )
        self._check_delays_with_mid_point(result_register, distance_dict)
        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0.99
        )
        self._check_fidelity(result_register)

    def test_egp_heralded_single_click_yaml(self):
        num_nodes = 6
        distances = [10.4, 23, 1, 4, 213.3e4, 15]
        sender_names = [f"sender_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        test_dir = pathlib.Path(__file__).parent.resolve()
        network_cfg = StackNetworkConfig.from_file(
            f"{test_dir}/yaml_configs/metro_hub_single-click-heralded.yaml"
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0
        )
        self._check_delays_with_mid_point(result_register, distance_dict)
        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0.99
        )
        self._check_fidelity(result_register)

    def test_egp_heralded_double_click(self):
        num_nodes = 6
        distances = [100, 23, 1e6, 1e3, 213.3e5, 15e6]
        sender_names = [f"creator_{i}" for i in range(num_nodes // 2)]
        receiver_names = [f"receiver_{i}" for i in range(num_nodes // 2)]

        link_cfg = HeraldedDoubleClickLinkConfig(
            p_loss_init=0,
            p_loss_length=0,
            speed_of_light=1e9,
            emission_fidelity=1,
        )

        network_cfg = create_metro_hub_network(
            node_names=sender_names + receiver_names,
            node_distances=distances,
            link_typ="heralded-double-click",
            link_cfg=link_cfg,
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(speed_of_light=1e9),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=0, max_multiplexing=3),
        )

        distance_dict = {
            node_name: dist
            for node_name, dist in zip(sender_names + receiver_names, distances)
        }

        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0
        )
        self._check_delays_with_mid_point(
            result_register, distance_dict, modulo_epr_round_time=True
        )
        result_register = self._perform_epr_test_run(
            network_cfg, sender_names, receiver_names, minimum_fidelity=0.99
        )
        self._check_fidelity(result_register)

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

        for sender_name, receiver_name in zip(sender_names, receiver_names):
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

    def _check_delays_with_mid_point(
        self,
        result_register: EGPEventRegistration,
        distances: Dict[str, float],
        modulo_epr_round_time=False,
    ):
        for received_egp in result_register.received_egp:
            dist1 = distances[received_egp.node_name]
            dist2 = distances[received_egp.peer_name]

            single_com_time = dist1 + dist2
            classical_handshake = single_com_time
            epr_round_time = 2 * max(dist1, dist2)
            expected_delay = classical_handshake + epr_round_time

            if not modulo_epr_round_time:
                self.assertAlmostEqual(expected_delay, received_egp.time, delta=1e-9)
            else:
                self.assertAlmostEqual(
                    0,
                    (received_egp.time - classical_handshake) % epr_round_time,
                    delta=1e-9,
                )

    def _check_fidelity(self, result_register: EGPEventRegistration):
        received_egp_with_full_dm = [received_egp for received_egp in result_register.received_egp if received_egp.dm.shape[0] > 2]
        # The protocol will discard qubits after registering the results, thereby destroying half of the state.
        # The second party to look at the qubit state, will thus see a DM with only one qubit.
        self.assertEqual(len(received_egp_with_full_dm), len(result_register.received_egp)/2)

        for received_egp in received_egp_with_full_dm:
            fid = calculate_fidelity_epr(
                received_egp.dm, received_egp.result.bell_state
            )
            self.assertGreater(fid, 0.99)


if __name__ == "__main__":
    unittest.main()
