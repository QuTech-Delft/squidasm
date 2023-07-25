from typing import List

from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket

from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


def from_bit_string(string: str) -> List[int]:
    bits = []
    for i in range(len(string)):
        bit = int(string[i])
        assert bit == 0 or bit == 1
        bits.append(bit)
    return bits


def to_bit_string(bits: List[int]) -> str:
    string = ""
    for bit in bits:
        string += str(bit)
    return string


class AliceProgram(Program):
    PEER_NAME = "Bob"

    def __init__(self, message: List[int]):
        self._message = message

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        logger = LogManager.get_stack_logger("AliceProgram")

        for i, bit in enumerate(self._message):
            logger.debug(f"Start round: {i}")
            if not (bit == 0 or bit == 1):
                logger.warning(f"Element {i} of message is not 0 or 1")

            # Generate two encryption bits from EPR
            q1, q2 = epr_socket.create_keep(number=2)
            q1.H()
            q2.H()
            m1 = q1.measure()
            m2 = q2.measure()
            yield from connection.flush()
            logger.info(f"Measured qubits: {m1} {m2}")

            # Bit indicating if bob should continue listening, 0 if this is the last bit, else 1
            bit_continue = int(i < len(self._message) - 1)

            # Send encrypted data bit and bit_continue
            bits_to_send = [bit ^ m1, bit_continue ^ m2]
            csocket.send(to_bit_string(bits_to_send))
            logger.info(f"Send bits: {bits_to_send[0]} {bits_to_send[1]}")

        logger.info("Finished")
        return {}


class BobProgram(Program):
    PEER_NAME = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket: Socket = context.csockets[self.PEER_NAME]
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        connection: BaseNetQASMConnection = context.connection

        logger = LogManager.get_stack_logger("BobProgram")

        bit_continue = 1
        received_message = []

        while bit_continue:
            logger.debug(f"Start round: {len(received_message)}")

            # Generate two encryption bits from EPR
            q1, q2 = epr_socket.recv_keep(number=2)
            q1.H()
            q2.H()
            m1 = q1.measure()
            m2 = q2.measure()
            yield from connection.flush()
            logger.info(f"Measured qubits: {m1} {m2}")

            # Receive classical communication
            bits_received = yield from csocket.recv()
            assert isinstance(bits_received, str)
            bits_received = from_bit_string(bits_received)
            logger.info(f"Received bits: {bits_received[0]} {bits_received[1]}")

            # XOR message with encryption bits
            bit = bits_received[0] ^ m1
            bit_continue = bits_received[1] ^ m2

            received_message.append(bit)

        logger.info(f"Finished, message received: {received_message}")
        return {"received message": received_message}
