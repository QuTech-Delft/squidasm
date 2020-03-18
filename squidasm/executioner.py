import logging
from enum import Enum
from dataclasses import dataclass

from pydynaa import EventExpression, EventType, Entity
from netsquid.nodes.node import Node
from netsquid.components.instructions import INSTR_INIT, INSTR_X, INSTR_H, INSTR_CNOT
from netsquid_magic.link_layer import LinkLayerCreate, LinkLayerRecv, ReturnType, RequestType, get_creator_node_id

from netqasm.executioner import Executioner
from netqasm.encoder import Instruction
from netqasm.parser import Address, Array, AddressMode


@dataclass
class CreateData:
    subroutine_id: int
    ent_info_address: int
    create_request: LinkLayerCreate
    pairs_left: int


@dataclass
class RecvData:
    subroutine_id: int
    ent_info_address: int
    recv_request: LinkLayerRecv
    pairs_left: int


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

        # Handle responsed for entanglement generation
        self._epr_response_handlers = self._get_epr_response_handlers()

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

    def _do_create_epr(self, subroutine_id, remote_node_id, purpose_id, q_address, arg_address, ent_info_address):
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has not network stack")
        create_request = self._get_create_request(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            arg_address=arg_address,
        )
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        num_qubits = len(self._shared_memories[app_id][q_address])
        assert num_qubits == create_request.number, "Not enough qubit addresses"
        create_id = self.network_stack.put(remote_node_id=remote_node_id, request=create_request)
        self._epr_create_requests[create_id] = CreateData(
            subroutine_id=subroutine_id,
            ent_info_address=ent_info_address,
            create_request=create_request,
            pairs_left=create_request.number,
        )

    def _get_create_request(self, subroutine_id, remote_node_id, purpose_id, arg_address):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        args = self._shared_memories[app_id][arg_address]
        # NOTE remote_node_id and purpose_id comes as direct arguments
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

    def _do_recv_epr(self, subroutine_id, remote_node_id, purpose_id, q_address, ent_info_address):
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has not network stack")
        recv_request = self._get_recv_request(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
        )
        # Check number of qubit addresses
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        num_qubits = len(self._shared_memories[app_id][q_address])
        self._epr_recv_requests[purpose_id].append(RecvData(
            subroutine_id=subroutine_id,
            ent_info_address=ent_info_address,
            recv_request=recv_request,
            pairs_left=num_qubits,
        ))
        self.network_stack.put(remote_node_id=remote_node_id, request=recv_request)

    def _get_recv_request(self, subroutine_id, remote_node_id, purpose_id):
        return LinkLayerRecv(
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
        )

    def _handle_epr_response(self, response):
        self._epr_response_handlers[response.type](response)

    def _handle_epr_err_response(self, response):
        raise RuntimeError(f"Got the following error from the network stack: {response}")

    def _handle_epr_ok_k_response(self, response):
        # NOTE this will probably be handled differently in an actual implementation
        # but is done in a simple way for now to allow for simulation
        # TODO cleanup this part
        creator_node_id = get_creator_node_id(self._node.ID, response)
        if creator_node_id == self._node.ID:
            create_id = response.create_id
            create_data = self._epr_create_requests[create_id]
            create_data.pairs_left -= 1
            if create_data.pairs_left == 0:
                self._epr_create_requests.pop(create_id)
            subroutine_id = create_data.subroutine_id
            ent_info_address = create_data.ent_info_address
        else:
            purpose_id = response.purpose_id
            recv_data = self._epr_recv_requests[purpose_id][0]
            recv_data.pairs_left -= 1
            if recv_data.pairs_left == 0:
                self._epr_recv_requests[purpose_id].pop(0)
            subroutine_id = recv_data.subroutine_id
            ent_info_address = recv_data.ent_info_address
        q_address = response.logical_qubit_id
        self._allocate_physical_qubit(subroutine_id, q_address)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        full_ent_info_address = self._get_address(
            app_id=app_id,
            operand=Array(
                address=Address(address=ent_info_address, mode=AddressMode.DIRECT),
                index=None,
            ),
        )
        ent_info = [entry.value if isinstance(entry, Enum) else entry for entry in response]
        self._shared_memories[app_id][full_ent_info_address] = ent_info

    def _handle_epr_ok_m_response(self, response):
        raise NotImplementedError

    def _handle_epr_ok_r_response(self, response):
        raise NotImplementedError

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
