import logging

from pydynaa import EventExpression, EventType, Entity

from netsquid.nodes.node import Node
from netsquid.components.instructions import INSTR_INIT, INSTR_X, INSTR_H, INSTR_CNOT

from netqasm.executioner import Executioner
from netqasm.encoder import Instruction


class NetSquidExecutioner(Executioner, Entity):

    NS_INSTR_MAPPING = {
        Instruction.INIT: INSTR_INIT,
        Instruction.X: INSTR_X,
        Instruction.H: INSTR_H,
        Instruction.CNOT: INSTR_CNOT,
    }

    def __init__(self, node, name=None, network_stack=None, num_qubits=5):
        """Executes a NetQASM using a NetSquid quantum processor to execute quantum instructions"""
        if not isinstance(node, Node):
            raise TypeError(f"node should be a Node, not {type(node)}")
        if name is None:
            name = node.name
        super().__init__(name=name, num_qubits=num_qubits)

        self._node = node
        qdevice = node.qmemory
        if qdevice is None:
            raise ValueError(f"The node needs to have a qdevice")
        self._qdevice = qdevice

        self._wait_event = EventType("WAIT", "event for waiting without blocking")

    @property
    def qdevice(self):
        return self._qdevice

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        position = self._get_position(subroutine_id=subroutine_id, address=address)
        ns_instr = self.__class__.NS_INSTR_MAPPING.get(instr)
        if ns_instr is None:
            raise RuntimeError(f"Don't know how to map the instruction {instr} to a netquid instruction")
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=[position])
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    def _do_two_qubit_instr(self, instr, subroutine_id, address1, address2):
        positions = self._get_positions(subroutine_id=subroutine_id, addresses=[address1, address2])
        ns_instr = self.__class__.NS_INSTR_MAPPING.get(instr)
        if ns_instr is None:
            raise RuntimeError("Don't know how to map the instruction {instr} to a netquid instruction")
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=positions)
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    def _do_meas(self, subroutine_id, q_address, c_operand):
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        outcome = self.qdevice.measure(position)[0][0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        try:
            self._set_address_value(app_id=app_id, operand=c_operand, value=outcome)
        except IndexError:
            logging.warning("Measurement outcome dropped since no more entries in classical register")

    def _do_wait(self):
        self._schedule_after(1, self._wait_event)
        yield EventExpression(source=self, event_type=self._wait_event)

    def _get_positions(self, subroutine_id, addresses):
        return [self._get_position(subroutine_id=subroutine_id, address=address) for address in addresses]

    def _get_position(self, subroutine_id, address):
        return self._get_position_in_unit_module(subroutine_id, address)

    def _get_unused_physical_qubit(self, address):
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in range(self.qdevice.num_positions):
            if physical_address not in self._used_physical_qubit_addresses:
                self._used_physical_qubit_addresses.append(physical_address)
                return physical_address
        raise RuntimeError("No more qubits left in qdevice")
