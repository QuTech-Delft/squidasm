import sys
from typing import Any, Dict, Generator

import netsquid as ns
from bitarray import bitarray

from pydynaa import EventExpression
from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network
from squidasm.util.qkd_routine import QKDRoutine
from squidasm.util.routines import recv_int, send_int


class SenderProgram(Program):
    PEER = "Bob"

    def __init__(self, msg: str):
        self.msg = msg

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]

        # Convert str to a bitarray
        bit_msg = bitarray()
        bitarray.frombytes(bit_msg, bytes(self.msg, "ascii"))
        # Make an estimate of the amount of epr pairs needed. On average only 50% will be in the correct basis.
        # To have a better probability of getting a sufficiently long key, a bit more epr pairs are used
        num_test = 30
        num_epr = int((len(bit_msg) + num_test) * 2.2 + 10)

        # Send protocol parameters to peer
        send_int(csocket, num_epr)
        send_int(csocket, num_test)

        # Run QKD protocol and generate a raw key
        raw_key, error_rate = yield from QKDRoutine.run(
            context,
            peer_name=self.PEER,
            is_init=True,
            num_epr=num_epr,
            num_test_bits=num_test,
        )

        if len(raw_key) < len(bit_msg):
            raise RuntimeError("Generated raw key is shorter than message")

        # Extend message to match raw key
        bit_diff = len(raw_key) - len(bit_msg)
        bit_msg.extend(bytearray(bit_diff))

        # Encrypt and send message
        encrypted_msg = raw_key ^ bit_msg
        csocket.send(encrypted_msg.to01())

        return {"raw_key": raw_key, "error_rate": error_rate}


class RecieverProgram(Program):
    PEER = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        csocket = context.csockets[self.PEER]

        # Receive parameters from peer
        num_epr = yield from recv_int(csocket)
        num_test = yield from recv_int(csocket)

        # Run the QKD protocol and generate the raw key
        raw_key, error_rate = yield from QKDRoutine.run(
            context,
            peer_name=self.PEER,
            is_init=False,
            num_epr=num_epr,
            num_test_bits=num_test,
        )

        # Get the message and decode it using the raw key
        recv_msg = yield from csocket.recv()
        assert isinstance(recv_msg, str)
        bit_msg = raw_key ^ bitarray(recv_msg)

        # First bit in byte can't be 1, due to ASCII encoding, so any 1 is an error.
        # This avoids ASCII decode raising an error
        for j in range(0, len(bit_msg), 8):
            bit_msg[j] = 0

        # Convert bitarray into str
        byte_msg = bit_msg.tobytes()
        msg = byte_msg.decode("ascii")

        return {"raw_key": raw_key, "message_received": msg, "error_rate": error_rate}


if __name__ == "__main__":
    # Fix seed on test runs to avoid accidentally causing a event where the key is too short for the message
    if "--test_run" in sys.argv:
        ns.set_random_state(seed=42)

    cfg = create_two_node_network(node_names=["Alice", "Bob"], link_noise=0.1)

    # Prepare the message and protocols
    message = "Hello world"
    alice_program = SenderProgram(message)
    bob_program = RecieverProgram()

    alice_results, bob_results = run(
        config=cfg, programs={"Alice": alice_program, "Bob": bob_program}, num_times=1
    )

    for i, (alice_result, bob_result) in enumerate(zip(alice_results, bob_results)):
        print(f"run {i}:")
        rk_alice = alice_result["raw_key"]
        rk_bob = bob_result["raw_key"]
        print(
            f"Alice:\nraw key: {rk_alice}\nMessage:\n{message}\n"
            f"Error rate estimate: {alice_result['error_rate'] * 100:.2f}%\n"
        )
        print(f"Bob\nraw key: {rk_bob}\nMessage:\n{bob_result['message_received']}\n")
        print(f"Key diff: {rk_bob ^ rk_alice}")
