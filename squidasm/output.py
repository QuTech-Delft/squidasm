from typing import List, Tuple, Set

from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.qubit import Qubit

from netqasm.output import InstrLogger as NQInstrLogger
from netqasm.output import QubitGroups, QubitState
from netqasm import instructions

from squidasm.ns_util import is_state_entangled
from squidasm.backend.glob import get_running_backend


class InstrLogger(NQInstrLogger):

    # Absulute IDs of all qubits in the simulation
    # List of (node_name, subroutine_id, qubit_id)
    _qubits: Set[Tuple[str, int, int]] = set()

    @classmethod
    def _get_qubit_groups(cls) -> QubitGroups:
        """Returns the current qubit groups in the simulation (qubits which have interacted
        and therefore may or may not be entangled)"""
        qubit_groups = {}
        for node_name, app_id, qubit_id in cls._qubits:
            qubit = cls._get_qubit_in_mem(
                node_name=node_name,
                app_id=app_id,
                qubit_id=qubit_id,
            )
            if qubit is None:
                continue
            group_id = hash(qubit.qstate)
            if group_id not in qubit_groups:
                qubit_groups[group_id] = {"qubits": []}
            qubit_groups[group_id]["qubits"].append([node_name, qubit_id])
            if "is_entangled" not in qubit_groups[group_id]:
                qubit_groups[group_id]["is_entangled"] = is_state_entangled(qubit.qstate)
        return qubit_groups

    def _update_qubits(
        self,
        subroutine_id: int,
        instr: instructions.base.NetQASMInstruction,
        qubit_ids: List[int],
    ) -> None:
        add_qubit_instrs = [
            instructions.core.InitInstruction,
            instructions.core.CreateEPRInstruction,
            instructions.core.RecvEPRInstruction,
        ]
        remove_qubit_instrs = [
            instructions.core.QFreeInstruction,
        ]
        node_name = self._get_node_name()
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        if any(isinstance(instr, cmd_cls) for cmd_cls in add_qubit_instrs):
            for qubit_id in qubit_ids:
                abs_id = node_name, app_id, qubit_id
                self.__class__._qubits.add(abs_id)
        elif any(isinstance(instr, cmd_cls) for cmd_cls in remove_qubit_instrs):
            for qubit_id in qubit_ids:
                abs_id = node_name, app_id, qubit_id
                if abs_id in self.__class__._qubits:
                    self.__class__._qubits.remove(abs_id)

    def _get_app_id(self, subroutine_id: int) -> int:
        """Returns the app ID for a given subroutine ID"""
        return self._executioner._get_app_id(subroutine_id=subroutine_id)

    @classmethod
    def _get_qubit_in_mem(
        cls,
        node_name: str,
        app_id: int,
        qubit_id: int,
    ) -> Qubit:
        """Returns the qubit object in memory"""
        backend = get_running_backend()
        executioner = backend.subroutine_handlers[node_name]._executioner
        return executioner._get_qubit(app_id=app_id, virtual_address=qubit_id)

    def _get_qubit_states(
        self,
        subroutine_id: int,
        qubit_ids: List[int],
    ) -> List[QubitState]:
        """Returns the reduced qubit states of the qubits involved in a command"""
        node_name = self._get_node_name()
        qubit_states = []
        for qubit_id in qubit_ids:
            app_id = self._get_app_id(subroutine_id=subroutine_id)
            qubit = self._get_qubit_in_mem(
                node_name=node_name,
                app_id=app_id,
                qubit_id=qubit_id,
            )
            if qubit is None:
                qubit_state = None
            else:
                qubit_state = qapi.reduced_dm(qubit).tolist()
            qubit_states.append(qubit_state)
        return qubit_states

    def _get_node_name(self) -> str:
        """Returns the name of this node"""
        return self._executioner._node.name
