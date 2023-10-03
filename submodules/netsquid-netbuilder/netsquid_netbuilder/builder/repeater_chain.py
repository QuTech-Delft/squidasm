from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type

from netsquid.components import Port
from netsquid_driver.EGP import EGPService
from netsquid_driver.entanglement_service import EntanglementService
from netsquid_driver.swap_asap_service import SwapASAPService
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.base_configs import RepeaterChainConfig
from netsquid_netbuilder.builder.builder_utils import (
    create_connection_ports,
    link_has_length,
    link_set_length,
)
from netsquid_netbuilder.builder.metro_hub import MetroHub
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceBuilder
from netsquid_netbuilder.network import Network
from netsquid_qrepchain.control_layer.swap_asap import SwapASAP
from netsquid_qrepchain.control_layer.swapasap_egp import (
    SwapAsapEndNodeLinkLayerProtocol,
)
from netsquid_qrepchain.processing_nodes.entanglement_magic import (
    SingleMemoryEntanglementMagic,
)

from squidasm.sim.stack.stack import ProcessingNode


@dataclass
class Chain:
    hub_1: MetroHub
    hub_2: MetroHub
    repeater_nodes: List[ProcessingNode] = field(default_factory=list)
    link_lengths: List[float] = field(default_factory=list)
    scheduler = None

    @property
    def name(self) -> str:
        return f"Chain ({self.hub_1.name}-{self.hub_2.name})"

    @property
    def repeater_nodes_dict(self) -> Dict[str, ProcessingNode]:
        return {node.name: node for node in self.repeater_nodes}


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
            raise NotImplementedError(
                "Currently we only support a single repeater chain"
            )
        self.chain_configs = chain_configs

    def register(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builders[key] = builder
        self.link_configs[key] = config

    def create_chain_objects(
        self, hubs: Dict[str, MetroHub]
    ) -> Dict[(str, str), Chain]:
        chains = {}
        if self.chain_configs is None:
            return chains
        for chain_config in self.chain_configs:
            chain = Chain(
                hub_1=hubs[chain_config.metro_hub1], hub_2=hubs[chain_config.metro_hub2]
            )
            chains[(chain_config.metro_hub1, chain_config.metro_hub2)] = chain
            chains[(chain_config.metro_hub2, chain_config.metro_hub1)] = chain

            chain.link_lengths = chain_config.lengths

        return chains

    def build_repeater_nodes(self, network: Network):
        if self.chain_configs is None:
            return

        for chain_config in self.chain_configs:

            base_repeater_node_name = (
                f"Chain_{chain_config.metro_hub1}-{chain_config.metro_hub2}_repeater_"
            )

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
                chain.repeater_nodes.append(node)

    def build_classical_connections(
        self,
        network: Network,
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
                raise ValueError(
                    f"The amount of repeater chain distances should be equal to"
                    f" the number of repeater nodes + 1 for chain {chain_config.metro_hub1}-{chain_config.metro_hub2}"
                )

            def _connect_nodes(
                node_1: ProcessingNode, node_2: ProcessingNode, length: float
            ):
                if hasattr(clink_config, "length"):
                    clink_config.length = length

                connection = clink_builder.build(node_1, node_2, clink_config)

                ports.update(
                    create_connection_ports(
                        node_1, node_2, connection, port_prefix="external"
                    )
                )

            # link repeater chain ends
            hub1_edge_repeater_node = chain.repeater_nodes[0]
            hub2_edge_repeater_node = chain.repeater_nodes[-1]

            clink_config = chain_config.clink_cfg

            _connect_nodes(
                hub1.hub_node, hub1_edge_repeater_node, chain.link_lengths[0]
            )
            _connect_nodes(
                hub2.hub_node, hub2_edge_repeater_node, chain.link_lengths[-1]
            )

            for chain_index in range(len(chain_config.repeater_nodes) - 1):
                n1 = chain.repeater_nodes[chain_index]
                n2 = chain.repeater_nodes[chain_index + 1]
                _connect_nodes(n1, n2, chain.link_lengths[chain_index + 1])

            # TODO

        return ports

    def build_links(
        self, network: Network
    ) -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}
        if self.chain_configs is None:
            return link_dict
        for chain_config in self.chain_configs:
            link_builder = self.link_builders[chain_config.link_typ]
            link_cfg_typ = self.link_configs[chain_config.link_typ]
            link_config = chain_config.link_cfg
            hub1 = network.hubs[chain_config.metro_hub1]
            hub2 = network.hubs[chain_config.metro_hub2]
            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]

            if isinstance(link_config, dict):
                link_config = link_cfg_typ(**chain_config.link_cfg)
            if not isinstance(link_config, link_cfg_typ):  # noqa
                raise TypeError(
                    f"Incorrect configuration provided. Got {type(link_config)},"
                    f" expected {link_cfg_typ.__name__}"
                )

            if not link_has_length(link_config):
                self._logger.warning(
                    f"Link type: {link_cfg_typ} has no length attribute length,"
                    f"metro hub lengths wil not be used for this link."
                )

            hub1_edge_repeater_node = chain.repeater_nodes[0]
            hub2_edge_repeater_node = chain.repeater_nodes[-1]

            def _create_link(
                node1: ProcessingNode, node2: ProcessingNode
            ) -> MagicLinkLayerProtocolWithSignaling:
                link = link_builder.build(node1, node2, link_config)
                self.protocol_controller.register(link)
                link_dict[(node1.name, node2.name)] = link
                link_dict[(node2.name, node1.name)] = link
                return link

            # Link end nodes on hub 1 side
            for hub1_end_node in hub1.end_nodes.values():
                link_set_length(
                    link_config,
                    hub1.end_node_lengths[hub1_end_node.name],
                    chain.link_lengths[0],
                )
                link_prot = _create_link(hub1_end_node, hub1_edge_repeater_node)
                link_prot.close()

            # Link end nodes on hub 2 side
            for hub2_end_node in hub2.end_nodes.values():
                link_set_length(
                    link_config,
                    chain.link_lengths[-1],
                    hub2.end_node_lengths[hub2_end_node.name],
                )
                link_prot = _create_link(hub2_edge_repeater_node, hub2_end_node)
                link_prot.close()

            # Link repeater nodes
            for idx in range(len(chain.repeater_nodes) - 1):
                length = chain.link_lengths[idx + 1]
                link_set_length(link_config, length / 2, length / 2)
                _create_link(chain.repeater_nodes[idx], chain.repeater_nodes[idx + 1])

        return link_dict

    def build_egp(self, network: Network) -> Dict[(str, str), EGPService]:
        egp_dict = {}
        for chain in network.chains.values():
            for hub1_end_node, hub2_end_node in itertools.product(
                chain.hub_1.end_nodes.values(), chain.hub_2.end_nodes.values()
            ):
                break
                egp_hub1_node = SwapAsapEndNodeLinkLayerProtocol(
                    hub1_end_node, hub2_end_node, chain
                )
                egp_hub2_node = SwapAsapEndNodeLinkLayerProtocol(
                    hub2_end_node, hub1_end_node, chain
                )

                egp_dict[(hub1_end_node.name, hub2_end_node.name)] = egp_hub1_node
                egp_dict[(hub2_end_node.name, hub1_end_node.name)] = egp_hub2_node

                # This only works if max 2 end nodes in network
                hub1_end_node.driver.add_service(EGPService, egp_hub1_node)
                hub2_end_node.driver.add_service(EGPService, egp_hub2_node)

                # self.protocol_controller.register(egp_hub1_node)
                # self.protocol_controller.register(egp_hub2_node)

            # self._setup_services(chain, network)

        return egp_dict

    def _setup_services(self, chain: Chain, network: Network):
        all_qnodes = (
            chain.repeater_nodes
            + list(chain.hub_2.end_nodes.values())
            + list(chain.hub_1.end_nodes.values())
        )

        for node in all_qnodes:
            driver = node.driver

            # incorporate this into Qdevice builder
            # TODO See how to incorporate the MoveProgram's, possibly it is fine once we put all device
            #  dependant things together in a package

            driver.services[EntanglementService] = SingleMemoryEntanglementMagic(
                node, num_parallel_links=1
            )  # Needs work

            # Investigate if this service is needed
            # driver.add_service(CutoffService, CutoffTimer(node=node, cutoff_time=cutoff_time))

        for idx, repeater in enumerate(chain.repeater_nodes):
            driver = repeater.driver

            driver.add_service(SwapASAPService, SwapASAP(repeater))  # Needs work