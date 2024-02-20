import random
import unittest
from typing import List

import netsquid as ns
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.scheduler.fifo import FIFOScheduleConfig
from netsquid_netbuilder.modules.scheduler.static import StaticScheduleConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.network_generation import create_metro_hub_network
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.util.test_protocol_scheduler import (
    SchedulerRequest,
    SchedulerResultRegistration,
    SchedulerTestProtocol,
)


class BaseSchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()
        self.builder = get_test_network_builder()
        self.result_register = SchedulerResultRegistration()

    def tearDown(self) -> None:
        pass

    @staticmethod
    def generate_requests(
        node_names: List[str], num_requests: int, delta_func: callable
    ) -> List[SchedulerRequest]:
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


class TestFIFOScheduler(BaseSchedulerTest):
    def test_1_no_overlap(self):
        """Test if all requests are completed in the expected time frame"""
        num_requests = 100
        num_nodes = 2
        distance = 100
        switch_time = 200
        speed_of_light = 1e9
        delay = 2 * distance / speed_of_light * speed_of_light + switch_time
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=switch_time),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return delay + 1

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertAlmostEqual(
                request.submit_time + delay,
                result.completion_time,
                delta=delay * 1e-9,
            )
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )

    def test_2_two_nodes_request_overlap(self):
        """Test if all requests are completed in the expected time frame"""
        num_requests = 200
        num_nodes = 2
        distance = 100
        switch_time = 200
        speed_of_light = 1e9
        delay = 2 * distance / speed_of_light * speed_of_light + switch_time
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=switch_time),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return 0.3 * delay

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertAlmostEqual(
                delay * (i + 1),
                result.completion_time,
                delta=delay * 1e-9,
            )
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )

    def test_3_multi_node_random_submission(self):
        """Test that with multiple nodes with overlapping requests all requests will eventually be delivered"""
        num_requests = 100
        num_nodes = 5
        distance = 100
        speed_of_light = 1e9
        delay = 2 * distance / speed_of_light * 1e9
        switch_time = 200
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(switch_time=switch_time),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return random.randint(0, int(delay) * 2)

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )

    def test_4_multiplexing(self):
        """Test if all requests are completed in the expected time frame when we have multiplexing enabled"""
        num_requests = 50
        num_nodes = 4
        max_multiplexing = 2
        distance = 100
        switch_time = 200
        speed_of_light = 1e9
        delay = 2 * distance / speed_of_light * speed_of_light + switch_time
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="fifo",
            schedule_cfg=FIFOScheduleConfig(
                switch_time=switch_time, max_multiplexing=max_multiplexing
            ),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return 1.2 * delay

        requests_pair1 = self.generate_requests(
            node_names[0:2], num_requests, delta_func=delta_func
        )
        requests_pair2 = self.generate_requests(
            node_names[2:4], num_requests, delta_func=delta_func
        )
        requests = requests_pair1 + requests_pair2
        requests.sort(key=lambda x: x.submit_time)

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertAlmostEqual(
                request.submit_time + delay,
                result.completion_time,
                delta=delay * 1e-9,
            )
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )


class TestStaticScheduler(BaseSchedulerTest):
    def test_1_no_overlap(self):
        """Test if all requests are completed in the expected time frame"""
        num_requests = 40
        num_nodes = 2
        distance = 100
        switch_time = 200
        speed_of_light = 1e9
        request_completion_time = 2 * distance / speed_of_light * speed_of_light
        time_window = request_completion_time * 1.5
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="static",
            schedule_cfg=StaticScheduleConfig(
                switch_time=switch_time, time_window=time_window
            ),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return time_window + switch_time

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertAlmostEqual(
                request.submit_time + request_completion_time,
                result.completion_time,
                delta=request_completion_time * 1e-9,
            )
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )

    def test_2_two_nodes_request_overlap(self):
        """Test if all requests are completed in the expected time frame"""
        num_requests = 200
        num_nodes = 2
        distance = 100
        switch_time = 200
        speed_of_light = 1e9
        request_completion_time = 2 * distance / speed_of_light * speed_of_light
        time_window = request_completion_time * 1.5
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="static",
            schedule_cfg=StaticScheduleConfig(
                switch_time=switch_time, time_window=time_window
            ),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return 0.3 * request_completion_time

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertAlmostEqual(
                i * (time_window + switch_time) + request_completion_time,
                result.completion_time,
                delta=request_completion_time * 1e-9,
            )
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )

    def test_3_multi_node_random_submission(self):
        """Test that with multiple nodes with overlapping requests all requests will eventually be delivered"""
        num_requests = 200
        num_nodes = 5
        distance = 100
        speed_of_light = 1e9
        request_completion_time = 2 * distance / speed_of_light * speed_of_light
        time_window = request_completion_time * 1.5
        switch_time = 200
        node_names = [f"node_{i}" for i in range(num_nodes)]

        network_cfg = create_metro_hub_network(
            node_names=node_names,
            node_distances=distance,
            link_typ="perfect",
            link_cfg=PerfectLinkConfig(speed_of_light=speed_of_light),
            clink_typ="default",
            clink_cfg=DefaultCLinkConfig(),
            schedule_typ="static",
            schedule_cfg=StaticScheduleConfig(
                switch_time=switch_time, time_window=time_window
            ),
        )
        network = self.builder.build(network_cfg)

        def delta_func():
            return random.randint(0, int(request_completion_time) * 2)

        requests = self.generate_requests(
            node_names, num_requests, delta_func=delta_func
        )

        protocols = {
            node_name: SchedulerTestProtocol(self.result_register, requests)
            for node_name in node_names
        }

        run(network, protocols)

        results = self.result_register.results
        self.assertEqual(len(requests) * 2, len(results))

        for i, request in enumerate(requests):
            result = results[2 * i]
            self.assertEqual(
                result.epr_measure_result, results[2 * i + 1].epr_measure_result
            )


if __name__ == "__main__":
    unittest.main()
