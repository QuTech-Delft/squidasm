from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    PEER_NAME = "Bob"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        result_list = []
        qubit = epr_socket.create_keep()[0]
        qubit.H()
        result = qubit.measure()

        # These operations work fine, as they do not attempt a value access
        result_list.append(result)
        print(type(result))

        # Uncomment will cause an error:
        # print(result_list)

        # Uncomment will cause an error:
        # result += 1

        # Uncomment will cause an error:
        # a = 5 if result else 0

        yield from connection.flush()

        print(result_list)
        print(f"Alice measures local EPR qubit: {result_list[0]}")

        return {}


class BobProgram(Program):
    PEER_NAME = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
        connection: BaseNetQASMConnection = context.connection

        qubit = epr_socket.recv_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        print(f"Bob measures local EPR qubit: {result}")

        return {}
