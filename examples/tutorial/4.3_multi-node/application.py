import netsquid as ns

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    PEER_BOB = "Bob"
    PEER_CHARLIE = "Charlie"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER_BOB, self.PEER_CHARLIE],
            epr_sockets=[self.PEER_BOB, self.PEER_CHARLIE],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket_bob = context.csockets[self.PEER_BOB]
        csocket_charlie = context.csockets[self.PEER_CHARLIE]
        # get EPR sockets
        epr_socket_bob = context.epr_sockets[self.PEER_BOB]
        epr_socket_charlie = context.epr_sockets[self.PEER_CHARLIE]
        # get connection to quantum network processing unit
        connection = context.connection

        # send a message to both nodes
        msg = "Hello from Alice"
        csocket_bob.send(msg)
        csocket_charlie.send(msg)
        print(f"{ns.sim_time()} ns: Alice sends: {msg} to Bob and Charlie")

        # Generate EPR pairs with both Bob and Charlie
        epr_qubit_bob = epr_socket_bob.create_keep()[0]
        epr_qubit_charlie = epr_socket_charlie.create_keep()[0]
        # Perform a bell state measurement on the qubit from Bob and the qubit from Charlie
        epr_qubit_bob.cnot(epr_qubit_charlie)
        epr_qubit_bob.H()
        m2 = epr_qubit_bob.measure()
        m1 = epr_qubit_charlie.measure()
        yield from connection.flush()

        print(
            f"{ns.sim_time()} ns: Alice finished EPR generation and local quantum operations"
        )
        csocket_charlie.send(str(int(m2)))
        csocket_charlie.send(str(int(m1)))

        print(
            f"{ns.sim_time()} ns: Alice sends corrections m1: {m1}, m2: {m2} to Charlie"
        )

        return {}


class BobProgram(Program):
    PEER = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket = context.csockets[self.PEER]
        # get EPR sockets
        epr_socket = context.epr_sockets[self.PEER]
        # get connection to quantum network processing unit
        connection = context.connection

        msg = yield from csocket.recv()
        print(f"{ns.sim_time()} ns: Bob receives: {msg}")

        # Generate and measure EPR pair with Alice
        qubit = epr_socket.recv_keep()[0]
        result = qubit.measure()
        yield from connection.flush()
        print(
            f"{ns.sim_time()} ns: Bob finished EPR generation and measures his qubit: {result}"
        )


class CharlieProgram(Program):
    PEER = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket = context.csockets[self.PEER]
        # get EPR sockets
        epr_socket = context.epr_sockets[self.PEER]
        # get connection to quantum network processing unit
        connection = context.connection

        msg = yield from csocket.recv()
        print(f"{ns.sim_time()} ns: Charlie receives: {msg}")

        # Generate EPR pair with Alice
        qubit = epr_socket.recv_keep()[0]
        yield from connection.flush()
        print(f"{ns.sim_time()} ns: Carlie finished EPR generation")

        # Receive corrections from Alice
        m2 = yield from csocket.recv()
        m1 = yield from csocket.recv()
        print(f"{ns.sim_time()} ns: Carlie received corrections: m1: {m1}, m2: {m2}")

        # Apply corrections
        if int(m1):
            qubit.X()
        if int(m2):
            qubit.Z()

        # Measure the EPR qubit
        result = qubit.measure()
        yield from connection.flush()
        print(
            f"{ns.sim_time()} ns: Carlie applied corrections and measures his qubit {result}"
        )
