import random
import unittest
from typing import List

import netsquid as ns
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.test_utils.network_generation import create_metro_hub_network
from netsquid_netbuilder.test_utils.scheduler_test_protocol import (
    SchedulerRequest,
    SchedulerResultRegistration,
    SchedulerTestProtocol,
)
from netsquid_netbuilder.test_utils.test_builder import get_test_network_builder


class TestFIFOScheduler(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        self.builder = get_test_network_builder()
        self.result_register = SchedulerResultRegistration()

    def tearDown(self) -> None:
        pass

    @staticmethod
    def generate_requests(
        node_names: List[str], num_requests: int, delta_func: callable
    ):
        requests = []
        submit_time = 0
        num_nodes = len(node_names)
        for _ in range(num_requests):
            r2 = r1 = random.randint(0, num_nodes - 1)
            while r1 == r2:
                r2 = random.randint(0, num_nodes - 1)

            request = SchedulerRequest(
                submit_time=submit_time,
                sender_name=node_names[r1],
                receiver_name=node_names[r2],
            )
            submit_time += delta_func()
            requests.append(request)
        return requests

    @unittest.skip("To be investigated")
    def test_1_no_overlap(self):
        """Test if all requests are completed in the expected time frame"""
        num_requests = 10
        num_nodes = 2
        distance = 100
        speed_of_light = 1e9
        # TODO it seems a in built 1000 extra ns is in the perfect link model, this is not desired
        delay = 2 * distance / speed_of_light * 1e9 + 1000

        network_cfg = create_metro_hub_network(
            nodes=num_nodes,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return delay + 1

        requests = self.generate_requests(
            list(network.end_nodes.keys()), num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in network.end_nodes.keys()
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            self.assertAlmostEqual(
                request.submit_time + delay,
                results[2 * i].completion_time,
                delta=delay * 1e-9,
            )

    @unittest.skip("To be investigated")
    def test_2_random_submission(self):
        """"""
        # TODO
        num_requests = 10
        num_nodes = 5
        distance = 10
        speed_of_light = 1e9
        delay = 2 * distance / speed_of_light * 1e9 + 1000

        network_cfg = create_metro_hub_network(
            nodes=num_nodes,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return random.randint(0, int(delay) * 2)

        requests = self.generate_requests(
            list(network.end_nodes.keys()), num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in network.end_nodes.keys()
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))


if __name__ == "__main__":
    unittest.main()
