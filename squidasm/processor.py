import logging

from pydynaa import EventExpression
from netsquid.components.qprocessor import QuantumProcessor
from netsquid.components.instructions import INSTR_INIT, INSTR_X, INSTR_H
from netqasm.processor import Processor
from netqasm.encoder import Instruction


class NetSquidProcessor(Processor):

    NS_INSTR_MAPPING = {
        Instruction.INIT: INSTR_INIT,
        Instruction.X: INSTR_X,
        Instruction.H: INSTR_H,
    }

    def __init__(self, name=None, qdevice=None, num_qubits=5):
        """Executes a NetQASM using a NetSquid quantum processor to execute quantum instructions"""
        super().__init__(name=name, num_qubits=num_qubits)
        if qdevice is None:
            qdevice = QuantumProcessor("QPD", num_qubits=num_qubits)
        if not isinstance(qdevice, QuantumProcessor):
            raise TypeError(f"qdevice should be a QuantumProcessor, not {type(qdevice)}")
        self._qdevice = qdevice

        self._qubit_positions_used = []

    def _do_one_single_qubit_instr(self, instr, address, index):
        position = self._get_position(address, index)
        ns_instr = self.__class__.NS_INSTR_MAPPING.get(instr)
        if ns_instr is None:
            raise RuntimeError("Don't know how to map the instruction {instr} to a netquid instruction")
        # self._qdevice.execute_instruction(ns_instr, qubit_mapping=[position], physical=False)  # TODO physical?
        self._qdevice.execute_instruction(ns_instr, qubit_mapping=[position])  # TODO physical?
        yield EventExpression(source=self._qdevice, event_type=self._qdevice.evtype_program_done)

    def _do_single_meas(self, q_address, q_index, c_address, c_index):
        position = self._get_position(q_address, q_index)
        outcome = self._qdevice.measure(position)[0][0]
        try:
            self._set_address_value(c_address, c_index, outcome)
        except IndexError:
            logging.warning("Measurement outcome dropped since no more entries in classical register")

    def _get_position(self, address, index):
        register = self._get_allocated_register(address)
        if index >= len(register):
            raise RuntimeError("Index out of bounds in quantum register with address {address}")
        position = register[index]
        return position

    def _allocate_new_quantum_register(self, num_entries):
        positions = self._get_unused_positions(num_positions=num_entries)
        return positions

    def _get_unused_positions(self, num_positions):
        used_positions = sum([used_positions for used_positions in self._quantum_registers.values()], [])
        new_positions = []
        for position in range(self._qdevice.num_positions):
            if position not in used_positions:
                new_positions.append(position)
                self._qubit_positions_used.append(position)
        if len(new_positions) < num_positions:
            raise MemoryError("No more qubits left to put in a register")
        return new_positions
