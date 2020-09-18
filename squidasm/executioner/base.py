from collections import namedtuple

from pydynaa import (
    EventExpression,
    EventType,
    Entity,
    EventHandler,
)
from netsquid.components.qmemory import MemPositionBusyError
from netsquid.nodes.node import Node
import netsquid as ns
from netsquid_magic.sleeper import Sleeper

from netqasm.executioner import Executioner, NotAllocatedError
from squidasm.output import InstrLogger

PendingEPRResponse = namedtuple("PendingEPRResponse", [
    "response",
    "epr_cmd_data",
    "pair_index",
])


class NetSquidExecutioner(Executioner, Entity):

    instr_logger_class = InstrLogger

    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None, instr_mapping=None):
        """Executes a NetQASM using a NetSquid quantum processor to execute quantum instructions"""
        if not isinstance(node, Node):
            raise TypeError(f"node should be a Node, not {type(node)}")
        if name is None:
            name = node.name
        super().__init__(name=name, instr_log_dir=instr_log_dir)

        if instr_mapping is None:
            raise ValueError("A NetSquidExecutioner needs to have an instruction mapping")
        self._instr_mapping = instr_mapping

        self._node = node
        qdevice = node.qmemory
        if qdevice is None:
            raise ValueError("The node needs to have a qdevice")
        self._qdevice = qdevice

        self._wait_event = EventType("WAIT", "event for waiting without blocking")

        # Sleeper
        self._sleeper = Sleeper()

        # Handler for calling epr data
        self._handle_pending_epr_responses_handler = EventHandler(lambda Event: self._handle_pending_epr_responses())
        self._handle_epr_data_handler = EventHandler(lambda Event: self._handle_epr_data())

    def _get_simulated_time(self):
        return ns.sim_time()

    @property
    def qdevice(self):
        return self._qdevice

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        position = self._get_position(subroutine_id=subroutine_id, address=address)
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} on qubit {position}")
        yield from self._execute_qdevice_instruction(
            ns_instr=ns_instr,
            qubit_mapping=[position],
        )

    def _do_single_qubit_rotation(self, instr, subroutine_id, address, angle):
        """Performs a single qubit rotation with the given angle"""
        position = self._get_position(subroutine_id=subroutine_id, address=address)
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} with angle {angle} on qubit {position}")
        yield from self._execute_qdevice_instruction(
            ns_instr=ns_instr,
            qubit_mapping=[position],
            angle=angle,
        )

    def _do_controlled_qubit_rotation(self, instr, subroutine_id, address1, address2, angle):
        positions = self._get_positions(subroutine_id=subroutine_id, addresses=[address1, address2])
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} on qubits {positions}")

        yield from self._execute_qdevice_instruction(
            ns_instr=ns_instr,
            qubit_mapping=positions,
            angle=angle
        )

    def _do_two_qubit_instr(self, instr, subroutine_id, address1, address2):
        positions = self._get_positions(subroutine_id=subroutine_id, addresses=[address1, address2])
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} on qubits {positions}")

        yield from self._execute_qdevice_instruction(
            ns_instr=ns_instr,
            qubit_mapping=positions,
        )

    def _execute_qdevice_instruction(self, ns_instr, qubit_mapping, **kwargs):
        if self.qdevice.busy:
            yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=qubit_mapping, **kwargs)
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    def _get_netsquid_instruction(self, instr):
        ns_instr = self._instr_mapping.get(instr.__class__)
        if ns_instr is None:
            raise RuntimeError(
                f"Don't know how to map the instruction {instr} (type {type(instr)}) to a netquid instruction")
        return ns_instr

    def _do_meas(self, subroutine_id, q_address):
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        self._logger.debug(f"Measuring qubit {position}")
        if self.qdevice.busy:
            yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)
        outcome = self.qdevice.measure(position)[0][0]
        return outcome

    def _do_wait(self):
        self._schedule_after(1, self._wait_event)
        yield EventExpression(source=self, event_type=self._wait_event)

    def _get_positions(self, subroutine_id, addresses):
        return [self._get_position(subroutine_id=subroutine_id, address=address) for address in addresses]

    def _get_position(self, subroutine_id=None, address=0, app_id=None):
        if app_id is None:
            if subroutine_id is None:
                raise ValueError("subroutine_id and app_id cannot both be None")
            app_id = self._get_app_id(subroutine_id=subroutine_id)
        return self._get_position_in_unit_module(app_id=app_id, address=address)

    def _get_unused_physical_qubit(self):
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in range(self.qdevice.num_positions):
            if physical_address not in self._used_physical_qubit_addresses:
                return physical_address
        raise RuntimeError("No more qubits left in qdevice")

    def _clear_phys_qubit_in_memory(self, physical_address):
        self.qdevice.set_position_used(False, physical_address)

    def _reserve_physical_qubit(self, physical_address):
        self.qdevice.set_position_used(True, physical_address)

    def _wait_to_handle_epr_responses(self):
        self._wait_once(
            handler=self._handle_pending_epr_responses_handler,
            expression=self._sleeper.sleep(),
        )

    def _get_qubit(self, app_id, virtual_address):
        try:
            phys_pos = self._get_position(app_id=app_id, address=virtual_address)
        except NotAllocatedError:
            return None
        try:
            qubit = self.qdevice._get_qubits(phys_pos)[0]
        except MemPositionBusyError:
            with self.qdevice._access_busy_memory([phys_pos]):
                self._logger.info("NOTE Accessing qubit from busy memory")
                qubit = self.qdevice._get_qubits(phys_pos, skip_noise=True)[0]
        return qubit
