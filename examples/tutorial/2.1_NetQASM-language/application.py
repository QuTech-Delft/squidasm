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

        qubit = epr_socket.create_keep()[0]
        qubit.H()
        result = qubit.measure()

        # The connection.flush() consists of two steps, proto compiling and then committing the proto subroutine
        subroutine = connection.compile()
        print(f"Alice's subroutine:\n\n{subroutine}\n")
        yield from connection.commit_subroutine(subroutine)

        print(f"Alice measures local EPR qubit: {result}")

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
