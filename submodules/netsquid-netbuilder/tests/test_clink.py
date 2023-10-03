import unittest
from typing import List

import netsquid as ns
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.clinks.instant import InstantCLinkConfig
from netsquid_netbuilder.modules.clinks.interface import ICLinkConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.test_utils.clink_test_protocol import (
    AliceProtocol,
    BobProtocol,
    ClassicalMessageResultRegistration,
)
from netsquid_netbuilder.test_utils.network_generation import create_2_node_network
from netsquid_netbuilder.test_utils.test_builder import get_test_network_builder


def create_test_network(typ: str, cfg: ICLinkConfig):
    return create_2_node_network("perfect", PerfectLinkConfig(), typ, cfg)


class TestCLinkBase(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        self.builder = get_test_network_builder()
        self.result_register = ClassicalMessageResultRegistration()

    def tearDown(self) -> None:
        pass

    def check_messages(
        self, messages: List[str], message_times: List[float], expected_delay=0.0
    ):
        self.assertEqual(len(self.result_register.rec_classical_msg), len(messages))
        for rec_msg, msg_time, msg in zip(
            self.result_register.rec_classical_msg, message_times, messages
        ):
            self.assertAlmostEqual(rec_msg[0], msg_time + expected_delay, delta=1e-21)
            self.assertEqual(msg, rec_msg[1])


class TestInstantCLink(TestCLinkBase):
    def test_1(self):
        network_cfg = create_test_network("instant", InstantCLinkConfig())
        network = self.builder.build(network_cfg)

        messages = ["hi", "hello", "good day", "how are you doing"]
        message_times = [1, 32, 44.2, 1000_3435.2]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, message_times)

    def test_2_same_time_ordering(self):
        network_cfg = create_test_network("instant", InstantCLinkConfig())
        network = self.builder.build(network_cfg)

        messages = ["hi", "hello", "good day", "how are you doing"]
        message_times = [1, 1, 1, 1]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, message_times)

    def test_3_delayed_listen(self):
        network_cfg = create_test_network("instant", InstantCLinkConfig())
        network = self.builder.build(network_cfg)

        messages = ["A", "B", "C", "D", "E", "F"]
        message_times = [1, 1, 1, 3, 3, 3]
        expected_times = [2, 2, 2, 3, 3, 3]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register, listen_delay=2)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, expected_times)


class TestDefaultCLink(TestCLinkBase, unittest.TestCase):
    def test_1_delay(self):
        delay = 2030.3
        network_cfg = create_test_network("default", DefaultCLinkConfig(delay=delay))
        network = self.builder.build(network_cfg)

        messages = ["hi", "hello", "good day", "how are you doing"]
        message_times = [1, 32, 44.2, 1000_3435.2]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, message_times, expected_delay=delay)

    def test_2_length(self):
        length = 203
        speed_of_light = 33.6
        delay = length / speed_of_light * 1e9
        network_cfg = create_test_network(
            "default", DefaultCLinkConfig(length=length, speed_of_light=speed_of_light)
        )
        network = self.builder.build(network_cfg)

        messages = ["hi", "hello", "good day", "how are you doing"]
        message_times = [1, 32, 44.2, 1000_3435.2]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, message_times, expected_delay=delay)

    def test_3_delayed_listen(self):
        delay = 0.5
        network_cfg = create_test_network("default", DefaultCLinkConfig(delay=delay))
        network = self.builder.build(network_cfg)

        messages = ["A", "B", "C", "D", "E", "F"]
        message_times = [1, 1, 1, 3, 3, 3]
        expected_times = [2, 2, 2, 3 + delay, 3 + delay, 3 + delay]

        alice = AliceProtocol(self.result_register, messages, message_times)
        bob = BobProtocol(self.result_register, listen_delay=2)

        run(network, {"Alice": alice, "Bob": bob})

        self.check_messages(messages, expected_times)


if __name__ == "__main__":
    unittest.main()
