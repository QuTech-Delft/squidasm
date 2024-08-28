import unittest
from dataclasses import dataclass
from typing import Dict, List

import netsquid as ns
from netsquid_netbuilder.util.network_generation import (
    create_complete_graph_network_simplified,
)

from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


@dataclass
class ReceivedMessage:
    """Class for registering information about messages received"""

    message: str
    """Message sent"""
    time_stamp: float
    """Time stamp when message was received"""


class SenderProgram(Program):
    def __init__(self, per_peer_messages: Dict[str, List[str]]):
        """
        Test program to send out messages
        :param per_peer_messages: Dictionary with keys being node names to send messages to
         and values being a list of messages to send
        """
        self.per_peer_messages = per_peer_messages

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="test_program",
            csockets=list(self.per_peer_messages.keys()),
            epr_sockets=[],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        for peer, messages in self.per_peer_messages.items():
            csocket = context.csockets[peer]
            for message in messages:
                csocket.send(message)

        # Hacky way of ensuring that the run method is a generator, otherwise test crashes
        yield from context.connection.flush()
        return {"complete": True}


class ReceiverProgram(Program):
    def __init__(self, per_peer_expect_num_messages: Dict[str, int]):
        """
        Test program to receive messages.
        :param per_peer_expect_num_messages: Dictionary with keys being node names of where we expect
         to receive messages from. Values are the number of messages we expect.
        """
        self.per_peer_expect_num_messages = per_peer_expect_num_messages

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="test_program",
            csockets=list(self.per_peer_expect_num_messages.keys()),
            epr_sockets=[],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        per_node_received_messages = {}
        start_time = ns.sim_time()
        # Per peer loop
        for peer, expected_num_messages in self.per_peer_expect_num_messages.items():
            csocket = context.csockets[peer]
            per_node_received_messages[peer] = []
            # Per message loop
            for _ in range(expected_num_messages):
                message = yield from csocket.recv()
                received_time = ns.sim_time() - start_time
                per_node_received_messages[peer].append(
                    ReceivedMessage(str(message), received_time)
                )

        return {
            "complete": True,
            "per_node_received_messages": per_node_received_messages,
        }


class TestClassicalCommunication(unittest.TestCase):
    def setUp(self) -> None:
        ns.sim_reset()

    def tearDown(self) -> None:
        pass

    def _check_results_per_node(self, results_per_node: List[List[dict]], delay: float):
        """Utility method to check that all programs completed,
        that all messages arrived at the same expected delay and
        that the message content is equal to the message index,
         in order to check that message ordering is identical to ordering of sending the messages"""
        for results in results_per_node:
            for result in results:
                self.assertTrue(result["complete"])

                if "per_node_received_messages" in result.keys():
                    for node, received_messages in result[
                        "per_node_received_messages"
                    ].items():
                        for i, received_message in enumerate(received_messages):
                            self.assertAlmostEqual(received_message.time_stamp, delay)
                            self.assertEqual(received_message.message, str(i))

    def test_two_nodes(self):
        delay = 10
        network_cfg = create_complete_graph_network_simplified(
            node_names=["Alice", "Bob"], clink_delay=delay
        )
        send_messages = {"Bob": ["0"]}

        sender_program = SenderProgram(send_messages)
        receiver_program = ReceiverProgram(per_peer_expect_num_messages={"Alice": 1})
        results_per_node = run(
            config=network_cfg,
            programs={"Alice": sender_program, "Bob": receiver_program},
            num_times=1,
        )
        self._check_results_per_node(results_per_node, delay)

    def test_multi_node(self):
        delay = 5
        senders = [f"sender_{i}" for i in range(4)]
        receivers = [f"receiver_{i}" for i in range(5)]
        network_cfg = create_complete_graph_network_simplified(
            node_names=senders + receivers, clink_delay=delay
        )

        send_messages = {receiver: ["0"] for receiver in receivers}
        per_peer_expect_num_messages = {sender: 1 for sender in senders}

        programs = {}
        for sender in senders:
            programs[sender] = SenderProgram(send_messages)
        for receiver in receivers:
            programs[receiver] = ReceiverProgram(per_peer_expect_num_messages)
        results_per_node = run(config=network_cfg, programs=programs, num_times=1)

        self._check_results_per_node(results_per_node, delay)

    def test_message_ordering(self):
        delay = 15
        num_messages = 6
        senders = [f"sender_{i}" for i in range(4)]
        receivers = [f"receiver_{i}" for i in range(5)]
        network_cfg = create_complete_graph_network_simplified(
            node_names=senders + receivers, clink_delay=delay
        )

        send_messages = {
            receiver: [str(i) for i in range(num_messages)] for receiver in receivers
        }
        per_peer_expect_num_messages = {sender: num_messages for sender in senders}

        programs = {}
        for sender in senders:
            programs[sender] = SenderProgram(send_messages)
        for receiver in receivers:
            programs[receiver] = ReceiverProgram(per_peer_expect_num_messages)
        results_per_node = run(config=network_cfg, programs=programs, num_times=1)

        self._check_results_per_node(results_per_node, delay)


if __name__ == "__main__":
    unittest.main()
