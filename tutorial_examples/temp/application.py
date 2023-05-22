from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit

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
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        # Generate and measure an EPR pair after a Hadamard num_epr_rounds times
        measurements = []
        meas2 = []
        for _ in range(self._num_epr_rounds):
            q1 = Qubit(connection)
            q2 = Qubit(connection)
            #q1.Z()
            q1.cnot(q2)
            m = q1.measure()
            m2 = q2.measure()
            measurements.append(m)
            meas2.append(m2)
            yield from connection.flush()

        measurements = [int(r) for r in measurements]
        meas2 = [int(r) for r in meas2]

        return {"measurements": measurements, "meas2": meas2}


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
        csocket: Socket = context.csockets[self.PEER_NAME]
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        connection: BaseNetQASMConnection = context.connection

        yield from connection.flush()

        return



