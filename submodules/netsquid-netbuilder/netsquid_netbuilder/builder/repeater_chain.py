from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from netsquid.components import Port
from netsquid.nodes import Node
from netsquid_driver.EGP import EGPService

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.photonic_interface_interface import (
    IPhotonicInterfaceBuilder,
    IPhotonicInterfaceConfig,
)
from netsquid_netbuilder.base_configs import RepeaterChainConfig
from netsquid_netbuilder.builder.builder_utils import (
    create_connection_ports,
    link_has_length,
    link_set_length,
)
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceBuilder
from netsquid_netbuilder.network import Network, Chain, MetroHub
from netsquid_netbuilder.modules.qrep_chain_control.interface import IQRepChainControlBuilder, IQRepChainControlConfig

from netsquid_netbuilder.nodes import QDeviceNode, RepeaterNode

if TYPE_CHECKING:
    from netsquid_netbuilder.builder.network_builder import ProtocolController


class ChainBuilder:
    def __init__(self, protocol_controller):
        self.protocol_controller: ProtocolController = protocol_controller
        self.qdevice_builders: Dict[str, Type[IQDeviceBuilder]] = {}
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}
        self.link_configs: Dict[str, Type[ILinkConfig]] = {}
        self.chain_configs: Optional[List[RepeaterChainConfig]] = None
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}
        self.clink_configs: Dict[str, Type[ICLinkConfig]] = {}
        self.photonic_interface_builders: Dict[str, Type[IPhotonicInterfaceBuilder]] = {}
        self.photonic_interface_configs: Dict[str, Type[IPhotonicInterfaceConfig]] = {}
        self.qrep_chain_control_builders: Dict[str, Type[IQRepChainControlBuilder]] = {}
        self.qrep_chain_control_configs: Dict[str, Type[IQRepChainControlConfig]] = {}
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

    def register_photonic_interface(
        self,
        key: str,
        builder: Type[IPhotonicInterfaceBuilder],
        config: Type[IPhotonicInterfaceConfig],
    ):
        self.photonic_interface_builders[key] = builder
        self.photonic_interface_configs[key] = config

    def register_qrep_chain_control(
        self,
        key: str,
        builder: Type[IQRepChainControlBuilder],
        config: Type[IQRepChainControlConfig],
    ):
        self.qrep_chain_control_builders[key] = builder
        self.qrep_chain_control_configs[key] = config

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
                f"c({chain_config.metro_hub1}-{chain_config.metro_hub2})_"
            )

            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]
            for repeater_index, repeater_node in enumerate(chain_config.repeater_nodes):
                if repeater_node.qdevice_typ not in self.qdevice_builders.keys():
                    # TODO improve exception
                    raise Exception(
                        f"No model of type: {repeater_node.qdevice_typ} registered"
                    )

                builder = self.qdevice_builders[repeater_node.qdevice_typ]

                repeater_name = base_repeater_node_name + f"{repeater_node.name}"
                qdevice = builder.build(
                    f"qdevice_{repeater_name}", qdevice_cfg=repeater_node.qdevice_cfg
                )

                node = RepeaterNode(
                    repeater_name,
                    qdevice=qdevice,
                    qdevice_type=repeater_node.qdevice_typ,
                )
                builder.build_services(node)

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
                node_1: Node, node_2: Node, length: float
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
                node1: QDeviceNode, node2: QDeviceNode
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
        num_repeater_chains = int(len(network.chains) / 2)
        egp_dict = {}

        if num_repeater_chains == 0:
            return egp_dict
        elif num_repeater_chains == 1:
            pass
        else:
            raise NotImplementedError("Simulation is currently limited to a single repeater chain") # noqa

        for chain_config in self.chain_configs:
            qrep_control_builder = self.qrep_chain_control_builders[chain_config.qrep_chain_control_typ] # noqa
            qrep_control_cfg_typ = self.qrep_chain_control_configs[chain_config.qrep_chain_control_typ] # noqa
            qrep_control_config = chain_config.qrep_chain_control_cfg
            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]

            if isinstance(qrep_control_config, dict):
                qrep_control_config = qrep_control_cfg_typ(**qrep_control_config)  # noqa
            if not isinstance(qrep_control_config, qrep_control_cfg_typ):  # noqa
                raise TypeError(
                    f"Incorrect configuration provided. Got {type(qrep_control_config)},"
                    f" expected {qrep_control_cfg_typ.__name__}"
                )
            egp_dict.update(qrep_control_builder.build(chain, network, qrep_control_config))

        return egp_dict

    def build_photonic_interfaces(self, network: Network):
        if self.chain_configs is None:
            return
        for chain_config in self.chain_configs:
            if chain_config.photonic_interface_typ is None:
                return

            photonic_interface_builder = self.photonic_interface_builders[chain_config.photonic_interface_typ]  # noqa
            photonic_interface_cfg_typ = self.photonic_interface_configs[chain_config.photonic_interface_typ]  # noqa
            photonic_interface_config = chain_config.photonic_interface_cfg
            chain = network.chains[(chain_config.metro_hub1, chain_config.metro_hub2)]

            if isinstance(photonic_interface_config, dict):
                photonic_interface_config = photonic_interface_cfg_typ(**photonic_interface_config)  # noqa
            if not isinstance(photonic_interface_config, photonic_interface_cfg_typ):  # noqa
                raise TypeError(
                    f"Incorrect configuration provided. Got {type(photonic_interface_config)},"
                    f" expected {photonic_interface_cfg_typ.__name__}"
                )

            link_keys = self._get_photonic_interface_link_keys(chain, chain_config.photonic_interface_loc)  # noqa

            for link_key in link_keys:
                photonic_interface = photonic_interface_builder.build(photonic_interface_config) # noqa
                link = network.links[link_key]
                link.magic_distributor.photonic_interface = photonic_interface

    @staticmethod
    def _get_photonic_interface_link_keys(
        chain: Chain, photonic_interface_loc
    ) -> List[Tuple[str, str]]:
        link_keys = []
        if photonic_interface_loc == "end":
            for node in chain.hub_1.end_nodes.values():
                link_keys.append((node.name, chain.repeater_nodes[0].name))
            for node in chain.hub_2.end_nodes.values():
                link_keys.append((node.name, chain.repeater_nodes[-1].name))
        elif photonic_interface_loc == "pre-end":
            if len(chain.repeater_nodes) < 3:
                raise ValueError(
                    f"pre-end photonic interface is only compatible when 3 or more repeater nodes "
                    f"are used"
                )
            link_keys.append(
                (chain.repeater_nodes[0].name, chain.repeater_nodes[1].name)
            )
            link_keys.append(
                (chain.repeater_nodes[-2].name, chain.repeater_nodes[-1].name)
            )
        else:
            raise ValueError(
                f"photonic_interface_loc: {photonic_interface_loc} is not a valid option"
            )
        return link_keys
