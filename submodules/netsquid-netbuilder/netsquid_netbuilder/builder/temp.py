from netsquid.components import QuantumProgram, INSTR_SWAP


class AbstractMoveProgram(QuantumProgram):

    def program(self):
        move_from, move_to = self.get_qubit_indices(2)
        self.apply(INSTR_SWAP, [move_from, move_to])

        yield self.run()
