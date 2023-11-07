import pathlib
import unittest
from typing import List

import netsquid as ns
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.network_generation import create_metro_hub_network
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.util.test_protocol_clink import (
    ClassicalMessageEventRegistration,
    ClassicalReceiverProtocol,
    ClassicalSenderProtocol,
)


class TestMetropolitanHub(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        self.builder = get_test_network_builder()

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
            protocols[sender_name] = sender
            protocols[receiver_name] = receiver
            expected_delay = distances[i] + distances[i + len(sender_names)]
            expected_delays[receiver_name] = expected_delays[
                sender_name
            ] = expected_delay

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


if __name__ == "__main__":
    unittest.main()
