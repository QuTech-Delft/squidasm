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

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        position = self._get_position(subroutine_id, address)
        ns_instr = self.__class__.NS_INSTR_MAPPING.get(instr)
        if ns_instr is None:
            raise RuntimeError("Don't know how to map the instruction {instr} to a netquid instruction")
        # self._qdevice.execute_instruction(ns_instr, qubit_mapping=[position], physical=False)  # TODO physical?
        self._qdevice.execute_instruction(ns_instr, qubit_mapping=[position])  # TODO physical?
        yield EventExpression(source=self._qdevice, event_type=self._qdevice.evtype_program_done)

    def _do_meas(self, subroutine_id, q_address, c_address):
        position = self._get_position(subroutine_id, q_address)
        outcome = self._qdevice.measure(position)[0][0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        try:
            self._set_address_value(app_id=app_id, address=c_address, value=outcome)
        except IndexError:
            logging.warning("Measurement outcome dropped since no more entries in classical register")

    def _get_position(self, subroutine_id, address):
        return self._get_position_in_unit_module(subroutine_id, address)

    def _get_unused_physical_qubit(self, address):
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in range(self._qdevice.num_positions):
            if physical_address not in self._used_physical_qubit_addresses:
                return physical_address
        raise RuntimeError("No more qubits left in qdevice")
