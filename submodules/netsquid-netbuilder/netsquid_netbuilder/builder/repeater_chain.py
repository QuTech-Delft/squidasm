from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.builder.metro_hub import MetroHub
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceBuilder
from squidasm.sim.stack.stack import ProcessingNode

import itertools
from typing import Dict, List, Optional, Type

from netsquid.components import Port
from netsquid.nodes import Node
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.base_configs import RepeaterChainConfig, MetroHubConfig
from netsquid_netbuilder.builder.builder_utils import create_connection_ports
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_netbuilder.modules.scheduler.interface import (
    IScheduleBuilder,
    IScheduleProtocol,
)
from netsquid_netbuilder.network import Network


@dataclass
class Chain:
    hub_1: MetroHub
    hub_2: MetroHub
    repeater_nodes: Dict[str, ProcessingNode] = field(default_factory=dict)
    scheduler = None


class ChainBuilder:
    def __init__(self, protocol_controller):
        # TODO add type to protocol controller
        self.protocol_controller = protocol_controller
        self.qdevice_builders: Dict[str, Type[IQDeviceBuilder]] = {}
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}
        self.link_configs: Dict[str, Type[ILinkConfig]] = {}
        self.chain_configs: Optional[List[RepeaterChainConfig]] = None
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}
        self.clink_configs: Dict[str, Type[ICLinkConfig]] = {}
        self._logger = LogManager.get_stack_logger(self.__class__.__name__)

    def register_qdevice(self, key: str, builder: Type[IQDeviceBuilder]):
        self.qdevice_builders[key] = builder

    def register_link(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builders[key] = builder
        self.link_configs[key] = config

    def register_clink(
        self, key: str, builder: Type[ICLinkBuilder], config: Type[ICLinkConfig]
    ):
        self.clink_builders[key] = builder
        self.clink_configs[key] = config

    def set_configs(self, chain_configs: List[RepeaterChainConfig]):
        if chain_configs is None:
            return
        if len(chain_configs) > 1:
            raise NotImplementedError("Currently we only support a single repeater chain")
        self.chain_configs = chain_configs

    def register(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builders[key] = builder
        self.link_configs[key] = config

    def create_chain_objects(self, hubs: Dict[str, MetroHub]) -> Dict[(str, str), Chain]:
        chains = {}
        if self.chain_configs is None:
            return chains
        for chain_config in self.chain_configs:
            chain = Chain(hub_1=hubs[chain_config.metro_hub1],
                          hub_2=hubs[chain_config.metro_hub2])
            chains[(chain_config.metro_hub1, chain_config.metro_hub2)] = chain
            chains[(chain_config.metro_hub2, chain_config.metro_hub1)] = chain

        return chains

    def build_repeater_nodes(self, network: Network):
        if self.chain_configs is None:
            return

        for chain_config in self.chain_configs:

            base_repeater_node_name = f"Chain_{chain_config.metro_hub1}-{chain_config.metro_hub2}_repeater_"

            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]
            for repeater_index, repeater_node in enumerate(chain_config.repeater_nodes):
                if repeater_node.qdevice_typ not in self.qdevice_builders.keys():
                    # TODO improve exception
                    raise Exception(
                        f"No model of type: {repeater_node.qdevice_typ} registered"
                    )

                builder = self.qdevice_builders[repeater_node.qdevice_typ]

                repeater_name = base_repeater_node_name + f"{repeater_index}"
                qdevice = builder.build(
                    f"qdevice_{repeater_name}", qdevice_cfg=repeater_node.qdevice_cfg
                )

                # TODO ProcessingNode is a very SquidASM centric object
                node = ProcessingNode(
                    repeater_name,
                    qdevice=qdevice,
                    qdevice_type=repeater_node.qdevice_typ,
                    hacky_is_squidasm_flag=False,  # Do not give repeater nodes a qnos
                )
                # Add node to chain object
                chain.repeater_nodes[repeater_name] = node

    def build_classical_connections(
        self, network: Network, hacky_is_squidasm_flag,
            metro_hub_configs: List[MetroHubConfig]
    ) -> Dict[(str, str), Port]:
        ports: Dict[(str, str), Port] = {}
        if self.chain_configs is None:
            return ports
        for chain_config in self.chain_configs:
            hub1 = network.hubs[chain_config.metro_hub1]
            hub2 = network.hubs[chain_config.metro_hub2]
            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]
            clink_builder = self.clink_builders[chain_config.clink_typ]
            clink_cfg_typ = self.clink_configs[chain_config.clink_typ]
            clink_config = chain_config.clink_cfg

            if isinstance(clink_config, dict):
                clink_config = clink_cfg_typ(**chain_config.link_cfg)
            if not isinstance(clink_config, clink_cfg_typ):  # noqa
                raise TypeError(
                    f"Incorrect configuration provided. Got {type(clink_config)},"
                    f" expected {clink_cfg_typ.__name__}"
                )

            if not hasattr(clink_config, "length"):
                self._logger.warning(
                    f"CLink type: {clink_cfg_typ} has no length attribute length,"
                    f"metro hub lengths wil not be used for this Clink."
                )

            if len(chain_config.lengths) != len(chain_config.repeater_nodes) + 1:
                raise ValueError(f"The amount of repeater chain distances"
                                 f" should be equal to the number of repeater nodes + 1")

            hub_to_hub_length = sum(chain_config.lengths)

            # Link end nodes with each other
            for n1, n2 in itertools.product(
                hub1.end_nodes.values(), hub2.end_nodes.values()
            ):
                assert isinstance(n1, ProcessingNode)
                assert isinstance(n2, ProcessingNode)
                clink_config = chain_config.clink_cfg
                if hasattr(clink_config, "length"):
                    clink_config.length = (
                        hub_to_hub_length + self._get_hub_end_node_length(metro_hub_configs, n1.name)
                        + self._get_hub_end_node_length(metro_hub_configs, n2.name)
                    )

                connection = clink_builder.build(n1, n2, clink_config)

                ports.update(
                    create_connection_ports(n1, n2, connection, port_prefix="host")
                )

                if hacky_is_squidasm_flag:
                    n1.register_peer(n2.ID)
                    n2.register_peer(n1.ID)
                    connection_qnos = clink_builder.build(n1, n2, link_cfg=clink_config)

                    n1.qnos_peer_port(n2.ID).connect(connection_qnos.port_A)
                    n2.qnos_peer_port(n1.ID).connect(connection_qnos.port_B)

            # link repeater chain
            # TODO

        return ports

    @staticmethod
    def _get_hub_end_node_length(metro_hub_configs: List[MetroHubConfig], node_name: str) -> float:
        for metro_hub_config in metro_hub_configs:
            for connection in metro_hub_config.connections:
                if node_name == connection.stack:
                    return connection.length
        raise ValueError(f"Could not find node {node_name} in any metro hub")
