from __future__ import annotations

from typing import TYPE_CHECKING, Dict, KeysView, List, Optional, Tuple

from netqasm.runtime.interface.logging import QubitGroup
from netsquid.components.qmemory import MemPositionBusyError
from netsquid.qubits import qubitapi as qapi

from squidasm.util.ns import is_state_entangled

if TYPE_CHECKING:
    from netsquid.nodes.node import Node as NetSquidNode

    from squidasm.run.multithread.runtime_mgr import SquidAsmRuntimeManager

_CURRENT_BACKEND: List[Optional[SquidAsmRuntimeManager]] = [None]


def get_running_backend(block: bool = True) -> Optional[SquidAsmRuntimeManager]:
    while True:
        backend = _CURRENT_BACKEND[0]
        if backend is not None:
            return backend
        if not block:
            return None


def get_current_nodes(block: bool = True) -> Dict[str, NetSquidNode]:
    backend = get_running_backend(block=block)
    if backend is None:
        raise RuntimeError("Backend is None")
    return backend.nodes  # type: ignore


def get_current_node_names(block: bool = True) -> KeysView[str]:
    backend = get_running_backend(block=block)
    if backend is None:
        raise RuntimeError("Backend is None")
    return backend.nodes.keys()  # type: ignore


def get_current_node_ids(block: bool = True) -> Dict[str, int]:
    backend = get_running_backend(block=block)
    if backend is None:
        raise RuntimeError("Backend is None")
    return {node_name: node.ID for node_name, node in backend.nodes.items()}


def get_current_app_node_mapping(block: bool = True) -> Dict[str, NetSquidNode]:
    backend = get_running_backend(block=block)
    if backend is None:
        raise RuntimeError("Backend is None")
    return backend.app_node_map  # type: ignore


def get_node_id_for_app(app_name: str) -> int:
    app_node_map = get_current_app_node_mapping()
    node = app_node_map.get(app_name)
    if node is None:
        raise ValueError(f"No app with name {app_name} mapped to a node")
    return node.ID  # type: ignore


def get_node_name_for_app(app_name: str) -> str:
    app_node_map = get_current_app_node_mapping()
    node = app_node_map.get(app_name)
    if node is None:
        raise ValueError(f"No app with name {app_name} mapped to a node")
    return node.name  # type: ignore


def get_node_id(name: str) -> int:
    current_node_ids = get_current_node_ids()
    node_id = current_node_ids.get(name)
    if node_id is None:
        raise ValueError(f"Unknown node with name {name}")
    return node_id


def get_node_name(node_id: int) -> str:
    current_node_ids = get_current_node_ids()
    for node_name, tmp_node_id in current_node_ids.items():
        if tmp_node_id == node_id:
            return node_name
    raise ValueError(f"Unknown node with id {node_id}")


def put_current_backend(backend: SquidAsmRuntimeManager) -> None:
    if _CURRENT_BACKEND[0] is not None:
        raise RuntimeError("Already a backend running")
    else:
        _CURRENT_BACKEND[0] = backend


def pop_current_backend() -> None:
    _CURRENT_BACKEND[0] = None


class QubitInfo:
    _qubits_in_use: Dict[Tuple[str, int], bool] = {}  # (node_name, phys_pos), is_used

    @classmethod
    def update_qubits_used(cls, node_name: str, pos: int, used: bool) -> None:
        cls._qubits_in_use[(node_name, pos)] = used

    @classmethod
    def get_qubit_groups(cls) -> Dict[int, QubitGroup]:
        backend = get_running_backend()
        if backend is None:
            raise RuntimeError("Backend is None")

        groups: Dict[int, QubitGroup] = {}

        for app_name, node in backend.app_node_map.items():
            num_pos = node.qmemory.num_positions
            for pos in range(num_pos):
                try:
                    qubit = node.qmemory.peek(pos, skip_noise=True)[0]
                except MemPositionBusyError:
                    with node.qmemory._access_busy_memory([pos]):
                        qubit = node.qmemory.peek(pos, skip_noise=True)[0]

                if qubit is None:
                    continue

                if (node.name, pos) in cls._qubits_in_use:
                    if not cls._qubits_in_use[(node.name, pos)]:
                        continue

                group_id = hash(qubit.qstate)
                if group_id not in groups:
                    groups[group_id] = QubitGroup(
                        is_entangled=None, qubit_ids=[], state=None
                    )
                groups[group_id].qubit_ids.append([app_name, pos])
                groups[group_id].is_entangled = is_state_entangled(qubit.qstate)

                if qubit.qstate.num_qubits == 1:
                    groups[group_id].state = qapi.reduced_dm(qubit).tolist()

        return groups
