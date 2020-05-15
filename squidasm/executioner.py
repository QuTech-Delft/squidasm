from enum import Enum
from collections import namedtuple

from pydynaa import EventExpression, EventType, Entity, EventHandler
from netsquid.nodes.node import Node
from netsquid.components.instructions import (
    INSTR_INIT,
    INSTR_X,
    INSTR_Y,
    INSTR_Z,
    INSTR_H,
    INSTR_K,
    INSTR_S,
    INSTR_T,
    INSTR_ROT_X,
    INSTR_ROT_Y,
    INSTR_ROT_Z,
    INSTR_CNOT,
    INSTR_CZ,
)
import netsquid as ns
from netsquid_magic.sleeper import Sleeper
from netsquid_magic.link_layer import LinkLayerCreate, ReturnType, RequestType, get_creator_node_id

from netqasm.executioner import Executioner
from netqasm.instructions import Instruction
from netqasm.network_stack import OK_FIELDS
from netqasm.parsing import parse_address


PendingEPRResponse = namedtuple("PendingEPRResponse", [
    "response",
    "epr_cmd_data",
    "pair_index",
])


class NetSquidExecutioner(Executioner, Entity):

    NS_INSTR_MAPPING = {
        Instruction.INIT: INSTR_INIT,
        Instruction.X: INSTR_X,
        Instruction.Y: INSTR_Y,
        Instruction.Z: INSTR_Z,
        Instruction.H: INSTR_H,
        Instruction.K: INSTR_K,
        Instruction.S: INSTR_S,
        Instruction.T: INSTR_T,
        Instruction.ROT_X: INSTR_ROT_X,
        Instruction.ROT_Y: INSTR_ROT_Y,
        Instruction.ROT_Z: INSTR_ROT_Z,
        Instruction.CNOT: INSTR_CNOT,
        Instruction.CPHASE: INSTR_CZ,
    }

    def __init__(self, node, name=None, network_stack=None, instr_log_dir=None):
        """Executes a NetQASM using a NetSquid quantum processor to execute quantum instructions"""
        if not isinstance(node, Node):
            raise TypeError(f"node should be a Node, not {type(node)}")
        if name is None:
            name = node.name
        super().__init__(name=name, instr_log_dir=instr_log_dir)

        self._node = node
        qdevice = node.qmemory
        if qdevice is None:
            raise ValueError(f"The node needs to have a qdevice")
        self._qdevice = qdevice

        self._wait_event = EventType("WAIT", "event for waiting without blocking")

        # Handle responsed for entanglement generation
        self._epr_response_handlers = self._get_epr_response_handlers()

        # Keep track of pending epr responses to handle
        self._pending_epr_responses = []

        # Sleeper
        self._sleeper = Sleeper()

        # Handler for calling epr data
        self._handle_pending_epr_responses_handler = EventHandler(lambda Event: self._handle_pending_epr_responses())
        self._handle_epr_data_handler = EventHandler(lambda Event: self._handle_epr_data())

    def _get_simulated_time(self):
        return ns.sim_time()

    def _get_epr_response_handlers(self):
        epr_response_handlers = {
            ReturnType.ERR: self._handle_epr_err_response,
            ReturnType.OK_K: self._handle_epr_ok_k_response,
            ReturnType.OK_M: self._handle_epr_ok_m_response,
            ReturnType.OK_R: self._handle_epr_ok_r_response,
        }

        return epr_response_handlers

    @property
    def qdevice(self):
        return self._qdevice

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        position = self._get_position(subroutine_id=subroutine_id, address=address)
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} on qubit {position}")
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=[position])
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    def _do_single_qubit_rotation(self, instr, subroutine_id, address, angle):
        """Performs a single qubit rotation with the given angle"""
        position = self._get_position(subroutine_id=subroutine_id, address=address)
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} with angle {angle} on qubit {position}")
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=[position], angle=angle)
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    def _do_two_qubit_instr(self, instr, subroutine_id, address1, address2):
        positions = self._get_positions(subroutine_id=subroutine_id, addresses=[address1, address2])
        ns_instr = self._get_netsquid_instruction(instr=instr)
        self._logger.debug(f"Doing instr {instr} on qubits {positions}")
        self.qdevice.execute_instruction(ns_instr, qubit_mapping=positions)
        yield EventExpression(source=self.qdevice, event_type=self.qdevice.evtype_program_done)

    @classmethod
    def _get_netsquid_instruction(cls, instr):
        ns_instr = cls.NS_INSTR_MAPPING.get(instr)
        if ns_instr is None:
            raise RuntimeError("Don't know how to map the instruction {instr} to a netquid instruction")
        return ns_instr

    def _do_meas(self, subroutine_id, q_address):
        position = self._get_position(subroutine_id=subroutine_id, address=q_address)
        self._logger.debug(f"Measuring qubit {position}")
        outcome = self.qdevice.measure(position)[0][0]
        return outcome

    def _do_wait(self):
        self._schedule_after(1, self._wait_event)
        yield EventExpression(source=self, event_type=self._wait_event)

    def _is_create_keep_request(self, request):
        return request.type == RequestType.K

    def _get_create_request(self, subroutine_id, remote_node_id, epr_socket_id, arg_array_address):
        purpose_id = self._network_stack._get_purpose_id(
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
        )
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        args = self._app_arrays[app_id][arg_array_address, :]
        args = [remote_node_id, purpose_id] + args

        # Use defaults if not specified
        expected_num_args = len(LinkLayerCreate._fields)
        if len(args) != expected_num_args:
            raise ValueError(f"Expected {expected_num_args} arguments, but got {len(args)}")
        kwargs = {}
        for arg, field, default in zip(args, LinkLayerCreate._fields, LinkLayerCreate.__new__.__defaults__):
            if arg is None:
                kwargs[field] = default
            else:
                kwargs[field] = arg
        kwargs["type"] = RequestType(kwargs["type"])

        return LinkLayerCreate(**kwargs)

    def _handle_epr_response(self, response):
        self._pending_epr_responses.append(response)
        self._handle_pending_epr_responses()

    def _handle_pending_epr_responses(self):
        # NOTE this will probably be handled differently in an actual implementation
        # but is done in a simple way for now to allow for simulation
        if len(self._pending_epr_responses) == 0:
            return

        response = self._pending_epr_responses[0]

        if response.type == ReturnType.ERR:
            self._handle_epr_err_response(response)
        else:
            self._logger.debug("Handling EPR OK ({response.type}) response from network stack")
            info = self._extract_epr_info(response=response)
            if info is not None:
                epr_cmd_data, pair_index, is_creator, request_key = info
                handled = self._epr_response_handlers[response.type](
                    epr_cmd_data=epr_cmd_data,
                    response=response,
                    pair_index=pair_index,
                )
            else:
                handled = False
            if handled:
                epr_cmd_data.pairs_left -= 1

                self._handle_last_epr_pair(
                    epr_cmd_data=epr_cmd_data,
                    is_creator=is_creator,
                    request_key=request_key,
                )

                self._store_ent_info(
                    epr_cmd_data=epr_cmd_data,
                    response=response,
                    pair_index=pair_index,
                )
                self._pending_epr_responses.pop(0)
            else:
                self._wait_once(
                    handler=self._handle_pending_epr_responses_handler,
                    expression=self._sleeper.sleep(),
                )
                return

        self._handle_pending_epr_responses()

    def _handle_epr_err_response(self, response):
        raise RuntimeError(f"Got the following error from the network stack: {response}")

    def _extract_epr_info(self, response):
        creator_node_id = get_creator_node_id(self._node.ID, response)

        # Retreive the data for this request (depending on if we are creator or receiver
        if creator_node_id == self._node.ID:
            is_creator = True
            create_id = response.create_id
            epr_cmd_data = self._epr_create_requests[create_id]
            request_key = create_id
        else:
            is_creator = False
            purpose_id = response.purpose_id
            if len(self._epr_recv_requests[purpose_id]) == 0:
                self._logger.debug(f"Since there is yet not recv request for purpose ID {purpose_id}, "
                                   "handling of epr will wait and try again.")
                return None
            epr_cmd_data = self._epr_recv_requests[purpose_id][0]
            request_key = purpose_id

        pair_index = epr_cmd_data.tot_pairs - epr_cmd_data.pairs_left

        return epr_cmd_data, pair_index, is_creator, request_key

    def _handle_last_epr_pair(self, epr_cmd_data, is_creator, request_key):
        # Check if this was the last pair
        if epr_cmd_data.pairs_left == 0:
            if is_creator:
                self._epr_create_requests.pop(request_key)
            else:
                self._epr_recv_requests[request_key].pop(0)

    def _store_ent_info(self, epr_cmd_data, response, pair_index):
        self._logger.debug("Storing entanglement information for pair {pair_index}")
        # Store the entanglement information
        ent_info = [entry.value if isinstance(entry, Enum) else entry for entry in response]
        ent_info_array_address = epr_cmd_data.ent_info_array_address
        # Start and stop of slice
        arr_start = pair_index * OK_FIELDS
        arr_stop = (pair_index + 1) * OK_FIELDS
        subroutine_id = epr_cmd_data.subroutine_id
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._app_arrays[app_id][ent_info_array_address, arr_start:arr_stop] = ent_info

    def _handle_epr_ok_k_response(self, epr_cmd_data, response, pair_index):

        # Extract qubit addresses
        subroutine_id = epr_cmd_data.subroutine_id
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        virtual_address = self._get_virtual_address_from_epr_data(epr_cmd_data, pair_index, app_id)

        # If the virtual address is currently in use, we should wait
        if self._has_virtual_address(app_id=app_id, virtual_address=virtual_address):
            self._logger.debug(f"Since virtual address {virtual_address} is in use, "
                               "handling of epr will wait and try again.")
            return False

        # Update qubit mapping
        physical_address = response.logical_qubit_id
        self._logger.debug(f"Virtual qubit address {virtual_address} will now be mapped to "
                           f"physical address {physical_address}")
        self._allocate_physical_qubit(
            subroutine_id=subroutine_id,
            virtual_address=virtual_address,
            physical_address=physical_address,
        )

        return True

    def _get_virtual_address_from_epr_data(self, epr_cmd_data, pair_index, app_id):
        q_array_address = epr_cmd_data.q_array_address
        array_entry = parse_address(f"@{q_array_address}[{pair_index}]")
        virtual_address = self._get_array_entry(app_id=app_id, array_entry=array_entry)
        return virtual_address

    def _handle_epr_ok_m_response(self, epr_cmd_data, response, pair_index):
        # M request are always handled
        return True

    def _handle_epr_ok_r_response(self, response):
        raise NotImplementedError
        return True

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
