from __future__ import annotations
import itertools

from netsquid_driver.entanglement_service import EntanglementService
from netsquid_driver.new_entanglment_service import NewEntanglementService
from netsquid_entanglementtracker.cutoff_service import CutoffService
from netsquid_entanglementtracker.cutoff_timer import CutoffTimer
from netsquid_netbuilder.builder.repeater_chain import Chain
from netsquid_netbuilder.modules.qrep_chain_control.interface import IQRepChainControlBuilder, IQRepChainControlConfig
from abc import ABC, abstractmethod
from typing import Dict

from netsquid_driver.EGP import EGPService
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap import SwapASAP
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap_egp import SwapAsapEndNodeLinkLayerProtocol
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap_service import SwapASAPService
from netsquid_netbuilder.network import Network
from netsquid_netbuilder.yaml_loadable import YamlLoadable

from squidasm.sim.stack.stack import ProcessingNode


class SwapASAPConfig(IQRepChainControlConfig):
    cutoff_time: float = None
    parallel_link_generation: bool = True


class SwapASAPBuilder(IQRepChainControlBuilder):
    @classmethod
    def build(cls, chain: Chain, network: Network, control_cfg: SwapASAPConfig) -> Dict[(str, str), EGPService]:

        temp_egp_dict: Dict[str, EGPService] = {}
        end_nodes = list(chain.hub_1.end_nodes.values()) + list(chain.hub_2.end_nodes.values())
        for end_node in end_nodes:
            repeater_egp = SwapAsapEndNodeLinkLayerProtocol(
                end_node, network.node_name_id_mapping, list(network.chains.values())[0]
            )
            end_node.driver.add_service(EGPService, repeater_egp)
            temp_egp_dict[end_node.name] = repeater_egp

        egp_dict: Dict[(str, str), EGPService] = {}
        for hub1_end_node, hub2_end_node in itertools.product(
            chain.hub_1.end_nodes.values(), chain.hub_2.end_nodes.values()
        ):

            egp_dict[(hub1_end_node.name, hub2_end_node.name)] = temp_egp_dict[
                hub1_end_node.name
            ]
            egp_dict[(hub2_end_node.name, hub1_end_node.name)] = temp_egp_dict[
                hub2_end_node.name
            ]

        cls._setup_services(chain, network, control_cfg)

        return egp_dict

    @classmethod
    def _setup_services(cls, chain: Chain, network: Network, control_cfg: SwapASAPConfig):
        all_chain_nodes = list(chain.hub_1.end_nodes.values()) + list(chain.hub_2.end_nodes.values()) + chain.repeater_nodes

        for node in all_chain_nodes:
            driver = node.driver

            local_link_dict = network.filter_for_node(node.name, network.links)

            local_distributor_dict = {
                node_name: link.magic_distributor
                for node_name, link in local_link_dict.items()
            }
            for magic_distributor in local_distributor_dict.values():
                magic_distributor.clear_all_callbacks()

            num_parallel_links = 2 if control_cfg.parallel_link_generation else 1

            driver.services[EntanglementService] = NewEntanglementService(
                node,
                local_distributor_dict,
                node_name_id_mapping=network.node_name_id_mapping,
                num_parallel_links=num_parallel_links
            )

            if control_cfg.cutoff_time:
                driver.add_service(CutoffService, CutoffTimer(node=node, cutoff_time=control_cfg.cutoff_time))

        for repeater in chain.repeater_nodes:
            driver = repeater.driver
            driver.add_service(SwapASAPService, SwapASAP(repeater))
