from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Type

from netsquid.components import Port
from netsquid.nodes import Node
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.base_configs import MetroHubConfig
from netsquid_netbuilder.builder.builder_utils import create_connection_ports
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder
from netsquid_netbuilder.modules.links.interface import ILinkBuilder
from netsquid_netbuilder.modules.scheduler.interface import (
    IScheduleBuilder,
    IScheduleProtocol,
)
from netsquid_netbuilder.network import Network


class MetroHubNode(Node):
    def __init__(
        self,
        name: str,
        node_id: Optional[int] = None,
    ) -> None:

        super().__init__(name, ID=node_id)


class HubBuilder:
    def __init__(self, protocol_controller):
        # TODO add type to protocol controller
        self.protocol_controller = protocol_controller
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}
        self.hub_configs: Optional[List[MetroHubConfig]] = None
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}
        self.scheduler_builders: Dict[str, Type[IScheduleBuilder]] = {}

    def register_clink(self, key: str, builder: Type[ICLinkBuilder]):
        self.clink_builders[key] = builder

    def set_configs(self, metro_hub_configs: List[MetroHubConfig]):
        self.hub_configs = metro_hub_configs

    def register_link(self, key: str, builder: Type[ILinkBuilder]):
        self.link_builders[key] = builder

    def register_scheduler(self, key: str, model: Type[IScheduleBuilder]):
        self.scheduler_builders[key] = model

    def build_hub_nodes(self) -> Dict[str, MetroHubNode]:
        hub_dict = {}
        if self.hub_configs is None:
            return hub_dict
        for hub_config in self.hub_configs:
            hub_dict[hub_config.name] = MetroHubNode(name=hub_config.name)

        return hub_dict

    def build_classical_connections(
        self, network: Network, hacky_is_squidasm_flag
    ) -> Dict[(str, str), Port]:
        ports: Dict[(str, str), Port] = {}
        if self.hub_configs is None:
            return ports
        for hub_config in self.hub_configs:
            clink_builder = self.clink_builders[hub_config.clink_typ]
            if hub_config.clink_cfg["distance"] is None:
                pass
                # Log warning not distance
            hub = network.hubs[hub_config.name]

            # Build hub - end node connections
            for connection_config in hub_config.connections:
                node = network.nodes[connection_config.stack]
                link_config = hub_config.clink_cfg
                hub_config.clink_cfg["distance"] = connection_config.distance

                connection = clink_builder.build(hub, node, link_config)

                ports.update(
                    create_connection_ports(hub, node, connection, port_prefix="host")
                )

            # Link end nodes with each other
            for connection_1_config, connection_2_config in itertools.combinations(
                hub_config.connections, 2
            ):
                n1 = network.nodes[connection_1_config.stack]
                n2 = network.nodes[connection_2_config.stack]

                link_config = hub_config.clink_cfg
                hub_config.clink_cfg["distance"] = (
                    connection_1_config.distance + connection_2_config.distance
                )
                connection = clink_builder.build(n1, n2, link_config)

                ports.update(
                    create_connection_ports(n1, n2, connection, port_prefix="host")
                )

                if hacky_is_squidasm_flag:
                    n1.register_peer(n2.ID)
                    n2.register_peer(n1.ID)
                    connection_qnos = clink_builder.build(n1, n2, link_cfg=link_config)

                    n1.qnos_peer_port(n2.ID).connect(connection_qnos.port_A)
                    n2.qnos_peer_port(n1.ID).connect(connection_qnos.port_B)

        return ports

    def build_links(
        self, network: Network
    ) -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}
        if self.hub_configs is None:
            return link_dict
        for hub_config in self.hub_configs:
            link_builder = self.link_builders[hub_config.link_typ]
            link_config = hub_config.link_cfg

            # if link_config["distance"] is None:
            #    pass
            # Log warning not distance

            for conn_1_cfg, conn_2_cfg in itertools.combinations(
                hub_config.connections, 2
            ):
                node1 = network.nodes[conn_1_cfg.stack]
                node2 = network.nodes[conn_2_cfg.stack]
                # TODO not sync with clink that uses distance + actually need individual distances
                link_config["length"] = conn_1_cfg.distance + conn_2_cfg.distance

                link_prot = link_builder.build(node1, node2, link_config)
                link_prot.close()

                self.protocol_controller.register(link_prot)
                link_dict[(node1.name, node2.name)] = link_prot
                link_dict[(node2.name, node1.name)] = link_prot

        return link_dict

    def build_schedule(self, network: Network) -> Dict[str, IScheduleProtocol]:
        schedule_dict = {}
        if self.hub_configs is None:
            return schedule_dict
        for hub_config in self.hub_configs:
            schedule_builder = self.scheduler_builders[hub_config.schedule_typ]

            node_names = [config.stack for config in hub_config.connections]
            schedule = schedule_builder.build(
                hub_config.name,
                network,
                node_names,
                schedule_config=hub_config.schedule_cfg,
            )
            self.protocol_controller.register(schedule)
            schedule_dict[hub_config.name] = schedule

            for node_name_combination in itertools.combinations(node_names, 2):
                link = network.links[node_name_combination]
                link.scheduler = schedule

        return schedule_dict
