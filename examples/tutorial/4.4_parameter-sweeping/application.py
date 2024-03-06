from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    PEER_NAME = "Bob"

    def __init__(self, num_epr_rounds):
        self._num_epr_rounds = num_epr_rounds

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        # Generate and measure an EPR pair after a Hadamard num_epr_rounds times
        measurements = []
        for _ in range(self._num_epr_rounds):
            qubit = epr_socket.create_keep()[0]
            qubit.H()
            m = qubit.measure()
            measurements.append(m)
            yield from connection.flush()

        measurements = [int(r) for r in measurements]
        return {"measurements": measurements}


class BobProgram(Program):
    PEER_NAME = "Alice"

    def __init__(self, num_epr_rounds):
        self._num_epr_rounds = num_epr_rounds

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        connection: BaseNetQASMConnection = context.connection

        # Generate and measure an EPR pair after a Hadamard num_epr_rounds times
        measurements = []
        for _ in range(self._num_epr_rounds):
            qubit = epr_socket.recv_keep()[0]
            qubit.H()
            m = qubit.measure()
            measurements.append(m)
            yield from connection.flush()

        measurements = [int(r) for r in measurements]
        return {"measurements": measurements}
