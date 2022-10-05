from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from squidasm.qoala.runtime.config import (
    GenericQDeviceConfig,
    LinkConfig,
    NVQDeviceConfig,
)
from squidasm.qoala.runtime.program import ProgramInstance

from .schedule import Schedule


@dataclass
class GlobalNodeInfo:
    """Node information available at runtime."""

    name: str
    id: int

    # total number of qubits
    num_qubits: int
    # number of communication qubits
    num_comm_qubits: int

    # coherence times for communication qubits
    comm_T1: int
    comm_T2: int

    # coherence times for memory (non-communication) qubits
    mem_T1: int
    mem_T2: int

    @classmethod
    def from_config(
        cls, name: str, id: int, config: Union[GenericQDeviceConfig, NVQDeviceConfig]
    ) -> GlobalNodeInfo:
        if isinstance(config, GenericQDeviceConfig):
            return GlobalNodeInfo(
                name=name,
                id=id,
                num_qubits=config.num_qubits,
                num_comm_qubits=config.num_comm_qubits,
                comm_T1=config.T1,
                comm_T2=config.T2,
                mem_T1=config.T1,
                mem_T2=config.T2,
            )
        else:
            assert isinstance(config, NVQDeviceConfig)
            return GlobalNodeInfo(
                name=name,
                num_qubits=config.num_qubits,
                num_comm_qubits=1,
                comm_T1=config.electron_T1,
                comm_T2=config.electron_T2,
                mem_T1=config.carbon_T1,
                mem_T2=config.carbon_T2,
            )


@dataclass
class GlobalLinkInfo:
    node_name1: str
    node_name2: str

    fidelity: float

    @classmethod
    def from_config(
        cls, node_name1: str, node_name2: str, config: LinkConfig
    ) -> GlobalLinkInfo:
        if config.typ == "perfect":
            return GlobalLinkInfo(
                node_name1=node_name1, node_name2=node_name2, fidelity=1.0
            )
        elif config.typ == "depolarise":
            return GlobalLinkInfo(
                node_name1=node_name1,
                node_name2=node_name2,
                fidelity=config.cfg.fidelity,  # type: ignore
            )
        else:
            raise NotImplementedError


class GlobalEnvironment:
    def __init__(self) -> None:
        # node ID -> node info
        self._nodes: Dict[int, GlobalNodeInfo] = {}

        # (node A ID, node B ID) -> link info
        # for a pair (a, b) there exists no separate (b, a) info (it is the same)
        self._links: Dict[Tuple[int, int], GlobalLinkInfo] = {}

    def get_nodes(self) -> Dict[int, GlobalNodeInfo]:
        return self._nodes

    def get_node_id(self, name: str) -> int:
        for id, node in self._nodes.items():
            if node.name == name:
                return id

    def set_nodes(self, nodes: Dict[int, GlobalNodeInfo]) -> None:
        self._nodes = nodes

    def add_node(self, id: int, node: GlobalNodeInfo) -> None:
        self._nodes[id] = node

    def get_links(self) -> Dict[int, GlobalLinkInfo]:
        return self._links

    def set_links(self, links: Dict[int, GlobalLinkInfo]) -> None:
        self._links = links

    def add_link(self, id: int, link: GlobalLinkInfo) -> None:
        self._links[id] = link


class LocalEnvironment:
    def __init__(
        self,
        global_env: GlobalEnvironment,
        node_id: int,
        local_schedule: Optional[Schedule] = None,
    ) -> None:
        self._global_env: GlobalEnvironment = global_env

        # node ID of self
        self._node_id: int = node_id

        self._programs: List[ProgramInstance] = []
        self._csockets: List[str] = []
        self._epr_sockets: List[str] = []

        self._local_schedule = local_schedule

    def get_global_env(self) -> GlobalEnvironment:
        return self._global_env

    def get_node_id(self) -> int:
        return self._node_id

    def register_program(self, program: ProgramInstance) -> None:
        self._programs.append(program)

    def open_epr_socket(self) -> None:
        pass

    def install_local_schedule(self, schedule: Schedule) -> None:
        self._local_schedule = schedule

    def get_all_node_names(self) -> List[str]:
        return list(self.get_global_env().get_nodes().values())


class ProgramEnvironment:
    """Environment interface given to a program"""

    pass
