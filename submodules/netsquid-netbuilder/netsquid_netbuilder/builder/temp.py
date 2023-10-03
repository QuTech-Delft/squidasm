from netsquid.components import INSTR_SWAP, QuantumProgram


class AbstractMoveProgram(QuantumProgram):
    def program(self):
        move_from, move_to = self.get_qubit_indices(2)
        self.apply(INSTR_SWAP, [move_from, move_to])

        yield self.run()
