import unittest

import netsquid as ns
from netsquid_driver.entanglement_agreement_service import (
    ReqEntanglementAgreement,
    ReqEntanglementAgreementAbort,
)
from netsquid_netbuilder.modules.links.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.run import run
from netsquid_netbuilder.util.network_generation import (
    create_2_node_network,
    create_metro_hub_network,
    create_qia_prototype_network,
)
from netsquid_netbuilder.util.test_builder import get_test_network_builder
from netsquid_netbuilder.util.test_protocol_agreement_service import (
    AgreementServiceResultRegistration,
    AgreementServiceTestProtocol,
)


class AgreementTestBase(unittest.TestCase):
    NETWORK_TYP = "2node"

    def setUp(self) -> None:
        ns.sim_reset()
        self.builder = get_test_network_builder()
        self.result_register = AgreementServiceResultRegistration()

    def tearDown(self) -> None:
        pass

    def check_last_agreement(
        self, result_register: AgreementServiceResultRegistration, delay: float
    ):
        submit_time_1 = result_register.submit_agreement[-1][0]
        submit_time_2 = result_register.submit_agreement[-2][0]
        rec_time_1 = result_register.rec_agreement[-1][0]
        rec_time_2 = result_register.rec_agreement[-2][0]

        max_time = max(submit_time_1, submit_time_2)

        # Agreement is signaled at the same time
        self.assertAlmostEqual(rec_time_1, rec_time_2, delta=1e-9)
        # Agreement is achieved when the last ask is made + time to travel to other node
        self.assertAlmostEqual(rec_time_1, max_time + delay, delta=1e-9)

    def check_abort(
        self, result_register: AgreementServiceResultRegistration, delay: float
    ):
        submit_time_ask_1 = result_register.submit_agreement[-1][0]
        submit_time_ask_2 = result_register.submit_agreement[-2][0]
        submit_time_abort = result_register.submit_abort[-1][0]

        assert submit_time_ask_1 == 0.0 or submit_time_ask_2 == 0.0
        max_time_ask = max(submit_time_ask_1, submit_time_ask_2)

        # 1) Abort arrived before second ask was made, nothing should happen
        # 2) Abort submitted before second ask was made, nothing should happen
        if submit_time_abort < max_time_ask:
            self.assertEqual(len(result_register.rec_agreement), 0)
            self.assertEqual(len(result_register.rec_abort), 0)
            return

        # Agreement should have been temporarily established, then abort made
        if submit_time_abort > max_time_ask:
            self.check_last_agreement(result_register, delay)
            rec_time_abort_1 = result_register.rec_abort[-1][0]
            rec_time_abort_2 = result_register.rec_abort[-2][0]
            self.assertAlmostEqual(rec_time_abort_1, rec_time_abort_2, delta=1e-9)
            self.assertAlmostEqual(
                rec_time_abort_1, submit_time_abort + delay, delta=1e-9
            )

    @staticmethod
    def create_network(network_typ, delay):

        speed_of_light_1km_per_ns = 1e9

        if network_typ == "2node":
            network_cfg = create_2_node_network(
                "perfect",
                PerfectLinkConfig(),
                "default",
                DefaultCLinkConfig(delay=delay),
            )
        elif network_typ == "metro":
            network_cfg = create_metro_hub_network(
                node_names=["Alice", "Bob", "Dummy1", "Dummy2"],
                node_distances=[1 / 3 * delay, 2 / 3 * delay, 10, 15],
                link_typ="perfect",
                link_cfg=PerfectLinkConfig(),
                clink_typ="default",
                clink_cfg=DefaultCLinkConfig(speed_of_light=speed_of_light_1km_per_ns),
            )
        elif network_typ == "qia_prototype":
            network_cfg = create_qia_prototype_network(
                nodes_hub1=["Alice", "Dummy1"],
                nodes_hub2=["Bob", "Dummy2"],
                node_distances_hub1=[1 / 5 * delay, 10],
                node_distances_hub2=[2 / 5 * delay, 10],
                num_nodes_repeater_chain=3,
                node_distances_repeater_chain=[
                    1 / 10 * delay,
                    1 / 10 * delay,
                    1 / 10 * delay,
                    1 / 10 * delay,
                ],
                link_typ="perfect",
                link_cfg=PerfectLinkConfig(),
                clink_typ="default",
                clink_cfg=DefaultCLinkConfig(speed_of_light=speed_of_light_1km_per_ns),
            )
        else:
            raise KeyError("Incorrect network_typ")

        return network_cfg

    def agreement_test(
        self, delay: float, termination_delay: float, offset: float, network_typ: str
    ):

        network_cfg = self.create_network(network_typ, delay)
        network = self.builder.build(network_cfg)

        alice = AgreementServiceTestProtocol(
            peer="Bob",
            result_reg=self.result_register,
            requests=[ReqEntanglementAgreement("Bob")],
            send_times=[0],
            termination_delay=termination_delay,
        )
        bob = AgreementServiceTestProtocol(
            peer="Alice",
            result_reg=self.result_register,
            requests=[ReqEntanglementAgreement("Alice")],
            send_times=[0 + offset],
            termination_delay=termination_delay,
        )

        run(network, {"Alice": alice, "Bob": bob})

        self.check_last_agreement(self.result_register, delay)

    def abort_test(
        self,
        delay: float,
        termination_delay: float,
        ask_offset: float,
        abort_offset: float,
        network_typ: str,
    ):

        network_cfg = self.create_network(network_typ, delay)
        network = self.builder.build(network_cfg)

        alice_requests = [
            ReqEntanglementAgreement("Bob"),
            ReqEntanglementAgreementAbort("Bob"),
        ]
        alice_send_times = [0, abort_offset]

        alice = AgreementServiceTestProtocol(
            peer="Bob",
            result_reg=self.result_register,
            requests=alice_requests,
            send_times=alice_send_times,
            termination_delay=termination_delay,
        )
        bob = AgreementServiceTestProtocol(
            peer="Alice",
            result_reg=self.result_register,
            requests=[ReqEntanglementAgreement("Alice")],
            send_times=[0 + ask_offset],
            termination_delay=termination_delay,
        )

        run(network, {"Alice": alice, "Bob": bob})

        self.check_abort(self.result_register, delay)

    def test_1(self):
        """Instant communication, same submission time"""
        self.agreement_test(
            delay=0, termination_delay=1, offset=0, network_typ=self.NETWORK_TYP
        )

    def test_2(self):
        """Instant communication, different submission time"""
        self.agreement_test(
            delay=0, termination_delay=30, offset=10, network_typ=self.NETWORK_TYP
        )

    def test_3(self):
        """normal communication, same submission time"""
        self.agreement_test(
            delay=10, termination_delay=30, offset=0, network_typ=self.NETWORK_TYP
        )

    def test_4(self):
        """normal communication, different submission time"""
        self.agreement_test(
            delay=10, termination_delay=100, offset=30, network_typ=self.NETWORK_TYP
        )

    def test_5(self):
        """normal communication, different submission time, second submission while first is in "flight" """
        self.agreement_test(
            delay=20, termination_delay=100, offset=10, network_typ=self.NETWORK_TYP
        )

    def test_6(self):
        """Instant communication, same submission time, abort afterwards"""
        self.abort_test(
            delay=0,
            termination_delay=30,
            ask_offset=0,
            abort_offset=1,
            network_typ=self.NETWORK_TYP,
        )

    def test_7(self):
        """Instant communication, different submission time, abort afterwards"""
        self.abort_test(
            delay=0,
            termination_delay=30,
            ask_offset=10,
            abort_offset=20,
            network_typ=self.NETWORK_TYP,
        )

    def test_8(self):
        """Instant communication, different submission time, abort before second ask"""
        self.abort_test(
            delay=0,
            termination_delay=30,
            ask_offset=20,
            abort_offset=10,
            network_typ=self.NETWORK_TYP,
        )

    def test_9(self):
        """normal communication, same submission time, abort after second ask"""
        self.abort_test(
            delay=5,
            termination_delay=50,
            ask_offset=0,
            abort_offset=10,
            network_typ=self.NETWORK_TYP,
        )

    def test_10(self):
        """normal communication, different submission time, requests in flight, abort before second ask made"""
        self.abort_test(
            delay=10,
            termination_delay=50,
            ask_offset=7,
            abort_offset=5,
            network_typ=self.NETWORK_TYP,
        )

    # TODO When an abort is made, we need to allow confirm requests created before this abort to create a temporary
    #  agreement
    @unittest.expectedFailure
    def test_11(self):
        """normal communication, different submission time, requests in flight, abort after second ask made"""
        self.abort_test(
            delay=10,
            termination_delay=50,
            ask_offset=5,
            abort_offset=7,
            network_typ=self.NETWORK_TYP,
        )

    def test_12(self):
        """normal communication, different submission time, abort after a lot later"""
        self.abort_test(
            delay=5,
            termination_delay=50,
            ask_offset=10,
            abort_offset=40,
            network_typ=self.NETWORK_TYP,
        )


class AgreementTestMetro(AgreementTestBase):
    NETWORK_TYP = "metro"


class AgreementTestQIAPrototype(AgreementTestBase):
    NETWORK_TYP = "qia_prototype"


if __name__ == "__main__":
    unittest.main()
