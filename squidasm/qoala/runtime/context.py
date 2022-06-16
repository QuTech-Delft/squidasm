from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from netqasm.sdk.network import NetworkInfo

from squidasm.qoala.runtime.environment import GlobalEnvironment

if TYPE_CHECKING:
    from squidasm.qoala.sim.host import Host


class NetSquidNetworkInfo(NetworkInfo):
    _global_env: GlobalEnvironment

    @classmethod
    def _get_node_id(cls, node_name: str) -> int:
        nodes = cls._global_env.get_nodes()
        for id, info in nodes.items():
            if info.name == node_name:
                return id
        raise ValueError(f"Node with name {node_name} not found")

    @classmethod
    def _get_node_name(cls, node_id: int) -> str:
        return cls._global_env.get_nodes()[node_id].name

    @classmethod
    def get_node_id_for_app(cls, app_name: str) -> int:
        return cls._get_node_id(node_name=app_name)

    @classmethod
    def get_node_name_for_app(cls, app_name: str) -> str:
        raise NotImplementedError
