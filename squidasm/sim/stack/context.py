from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from netqasm.sdk.network import NetworkInfo

if TYPE_CHECKING:
    from squidasm.sim.stack.host import Host


class NetSquidNetworkInfo(NetworkInfo):
    @classmethod
    def _get_node_id(cls, node_name: str) -> int:
        nodes = NetSquidContext.get_nodes()
        for id, name in nodes.items():
            if name == node_name:
                return id
        raise ValueError(f"Node with name {node_name} not found")

    @classmethod
    def _get_node_name(cls, node_id: int) -> str:
        return NetSquidContext.get_nodes()[node_id]

    @classmethod
    def get_node_id_for_app(cls, app_name: str) -> int:
        return cls._get_node_id(node_name=app_name)

    @classmethod
    def get_node_name_for_app(cls, app_name: str) -> str:
        raise NotImplementedError


class NetSquidContext:
    _protocols: Dict[str, Host] = {}
    _nodes: Dict[int, str] = {}

    @classmethod
    def get_nodes(cls) -> Dict[int, str]:
        return cls._nodes

    @classmethod
    def set_nodes(cls, nodes: Dict[int, str]) -> None:
        cls._nodes = nodes

    @classmethod
    def add_node(cls, id: int, node: str) -> None:
        cls._nodes[id] = node

    @classmethod
    def get_protocols(cls) -> Dict[str, Host]:
        return cls._protocols

    @classmethod
    def set_protocols(cls, protocols: Dict[str, Host]) -> None:
        cls._protocols = protocols

    @classmethod
    def add_protocol(cls, name: str, protocol: Host) -> None:
        cls._protocols[name] = protocol
