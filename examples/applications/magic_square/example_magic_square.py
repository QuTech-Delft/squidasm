import logging
from typing import List

import numpy
from netqasm.sdk.toolbox.measurements import parity_meas

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network
from squidasm.util.routines import recv_int


def get_default_strategy():
    return [
        ["XI", "XX", "IX"],  # row 0
        ["-XZ", "YY", "-ZX"],  # row 1
        ["IZ", "ZZ", "ZI"],  # row 2
    ]


class Player1Program(Program):
    PEER_NAME = "Player2"

    def __init__(self, row: int, strategy: List[List[str]]):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.strategy = strategy
        self.row = row
        if self.row >= len(self.strategy):
            raise ValueError(f"Not a row in the square {self.row}")

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="player1_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        self.logger.info("Creating shared state with other player...")
        # Create EPR pairs
        q1 = epr_socket.create_keep()[0]
        q2 = epr_socket.create_keep()[0]

        yield from connection.flush()
        self.logger.info("Finished creating shared state with other player...")

        csocket.send("")

        # Make sure we order the qubits consistently with connection
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if int(q1_ID) < int(q2_ID):
            qa = q1
            qc = q2
        else:
            qa = q2
            qc = q1

        # Perform the three measurements
        self.logger.info(f"Measuring {self.strategy[self.row][0]} ...")
        m0 = parity_meas([qa, qc], self.strategy[self.row][0])
        yield from connection.flush()
        self.logger.info(f"Outcome: {m0}")

        self.logger.info(f"Measuring {self.strategy[self.row][1]} ...")
        m1 = parity_meas([qa, qc], self.strategy[self.row][1])
        yield from connection.flush()
        self.logger.info(f"Outcome: {m1}")

        self.logger.info(f"Measuring {self.strategy[self.row][2]} ...")
        m2 = parity_meas([qa, qc], self.strategy[self.row][2])
        yield from connection.flush()
        self.logger.info(f"Outcome: {m2}")

        csocket.send("")

        # free qmemory
        qa.measure()
        qc.measure()
        yield from connection.flush()

        to_print = "\n\n"
        to_print += "==========================\n"
        to_print += "App connection: row is:\n"
        for _ in range(self.row):
            to_print += "(___)\n"
        to_print += f"({m0}{m1}{m2})\n"
        for _ in range(2 - self.row):
            to_print += "(___)\n"
        to_print += "==========================\n"
        to_print += "\n\n"
        self.logger.info(to_print)

        # Only needed for visualization: to check at which cell the row intersects with the column of the other player.
        csocket.send(str(self.row))
        p1_row = f"{m0},{m1},{m2}"
        csocket.send(p1_row)

        return {
            "row": [int(m0), int(m1), int(m2)],
            "row_index": self.row,
        }


class Player2Program(Program):
    PEER_NAME = "Player1"

    def __init__(self, col: int, strategy: List[List[str]]):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.strategy = strategy
        self.col = col
        if self.col >= len(self.strategy[0]):
            raise ValueError(f"Not a col in the square {self.col}")

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="player1_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection

        self.logger.info("Creating shared state with other player...")
        # Create EPR pairs
        q1 = epr_socket.recv_keep()[0]
        q2 = epr_socket.recv_keep()[0]

        yield from connection.flush()
        self.logger.info("Finished creating shared state with other player...")

        yield from csocket.recv()

        # Make sure we order the qubits consistently with Player1
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if int(q1_ID) < int(q2_ID):
            qb = q1
            qd = q2
        else:
            qb = q2
            qd = q1

        # Wait for player 1 to finish their measurements
        yield from csocket.recv()

        # Perform the three measurements
        self.logger.info(f"Measuring {self.strategy[0][self.col]} ...")
        m0 = parity_meas([qb, qd], self.strategy[0][self.col])
        connection.flush()
        self.logger.info(f"Outcome: {m0}")

        self.logger.info(f"Measuring {self.strategy[1][self.col]} ...")
        m1 = parity_meas([qb, qd], self.strategy[1][self.col])
        connection.flush()
        self.logger.info(f"Outcome: {m1}")

        self.logger.info(f"Measuring {self.strategy[2][self.col]} ...")
        m2 = parity_meas([qb, qd], self.strategy[2][self.col])
        yield from connection.flush()
        self.logger.info(f"Outcome: {m2}")

        # free qmemory
        qb.measure()
        qd.measure()
        yield from connection.flush()

        to_print = "\n\n"
        to_print += "==========================\n"
        to_print += "App connection: column is:\n"
        to_print += "(" + "_" * self.col + str(m0) + "_" * (2 - self.col) + ")\n"
        to_print += "(" + "_" * self.col + str(m1) + "_" * (2 - self.col) + ")\n"
        to_print += "(" + "_" * self.col + str(m2) + "_" * (2 - self.col) + ")\n"
        to_print += "==========================\n"
        to_print += "\n\n"
        self.logger.info(to_print)

        # Only needed for visualization: to check at which cell the column intersects with the row of the other player.
        player1_row = yield from recv_int(csocket)
        player1_outcomes = yield from csocket.recv()
        assert isinstance(player1_outcomes, str)
        player1_outcomes = player1_outcomes.split(",")

        col_outcomes = [int(m0), int(m1), int(m2)]

        square = [["", "", ""], ["", "", ""], ["", "", ""]]

        square[player1_row][0] = str(player1_outcomes[0])
        square[player1_row][1] = str(player1_outcomes[1])
        square[player1_row][2] = str(player1_outcomes[2])
        square[0][self.col] = str(col_outcomes[0])
        square[1][self.col] = str(col_outcomes[1])
        square[2][self.col] = str(col_outcomes[2])
        square[player1_row][
            self.col
        ] = f"{player1_outcomes[self.col]}/{col_outcomes[player1_row]}"

        return {
            "col_index": self.col,
            "col": col_outcomes,
            "square": square,
        }


if __name__ == "__main__":
    # Create a network configuration
    cfg = create_two_node_network(node_names=["Player1", "Player2"])

    # generate a game
    strategy = get_default_strategy()
    row = numpy.random.randint(0, 3)
    col = numpy.random.randint(0, 3)

    # Create instances of programs to run
    player1_program = Player1Program(row, strategy)
    player2_program = Player2Program(col, strategy)

    # toggle logging. Set to logging.INFO for logging of events.
    player1_program.logger.setLevel(logging.ERROR)
    player2_program.logger.setLevel(logging.ERROR)

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    player1_result, player2_result = run(
        config=cfg,
        programs={"Player2": player2_program, "Player1": player1_program},
        num_times=1,
    )
