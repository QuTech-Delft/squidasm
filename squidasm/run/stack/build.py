from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_netbuilder.builder.network_builder import NetworkBuilder, NodeBuilder
from netsquid_netbuilder.run import get_default_builder

if TYPE_CHECKING:
    from squidasm.sim.stack.stack import StackNode


class StackNodeBuilder(NodeBuilder):
    def build(self, config: NetworkConfig) -> Dict[str, StackNode]:
        nodes = {}
        for node_config in config.processing_nodes:
            node_name = node_config.name
            node_qdevice_typ = node_config.qdevice_typ

            if node_qdevice_typ not in self.qdevice_builders.keys():
                # TODO improve exception
                raise Exception(f"No model of type: {node_qdevice_typ} registered")

            builder = self.qdevice_builders[node_qdevice_typ]
            qdevice = builder.build(
                f"qdevice_{node_name}", qdevice_cfg=node_config.qdevice_cfg
            )

            nodes[node_name] = StackNode(
                node_name,
                qdevice=qdevice,
                qdevice_type=node_qdevice_typ,
            )
            self.qdevice_builders[node_qdevice_typ].build_services(nodes[node_name])
        return nodes


def create_stack_network_builder() -> NetworkBuilder:
    builder = get_default_builder()
    original_node_builder = builder.node_builder

    # replace the original node builder with new StackNodeBuilder
    builder.node_builder = StackNodeBuilder()
    # move over original qdevice builders to StackNodeBuilder
    builder.node_builder.qdevice_builders = original_node_builder.qdevice_builders

    return builder
