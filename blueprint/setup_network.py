from __future__ import annotations

import itertools
from typing import Dict, List, Type

from blueprint.base_configs import StackNetworkConfig
from blueprint.links import (
    DepolariseLinkConfig,
    HeraldedLinkConfig,
    NVLinkConfig,
)
from blueprint.qdevices import (
    GenericQDeviceConfig,
    NVQDeviceConfig,
    build_nv_qdevice,
    build_generic_qdevice,
)
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import (
    DepolariseWithFailureMagicDistributor,
    DoubleClickMagicDistributor,
    PerfectStateMagicDistributor,
)
from netsquid_nv.magic_distributor import NVSingleClickMagicDistributor
from netsquid_physlayer.heralded_connection import MiddleHeraldedConnection
from squidasm.sim.stack.stack import NodeStack, StackNetwork, ProcessingNode
from squidasm.sim.stack.egp import EgpProtocol


def fidelity_to_prob_max_mixed(fid: float) -> float:
    return (1 - fid) * 4.0 / 3.0


class ProtocolContext:
    def __init__(self, node: ProcessingNode,
                 links: Dict[str, MagicLinkLayerProtocolWithSignaling],
                 egp: Dict[str, EgpProtocol],
                 node_id_mapping: Dict[str, int]):
        self.node = node
        self.links = links
        self.egp = egp
        self.node_id_mapping = node_id_mapping


class Network:
    def __init__(self):
        self.nodes: Dict[str, ProcessingNode] = {}
        self.links: Dict[(str, str), MagicLinkLayerProtocolWithSignaling] = {}
        self.egp: Dict[(str, str), EgpProtocol] = {}
        self.node_name_id_mapping: Dict[str, int] = {}

    def get_protocol_context(self, node_id: str) -> ProtocolContext:
        node = self.nodes[node_id]
        links = self.filter_for_id(node_id, self.links)
        egp = self.filter_for_id(node_id, self.egp)

        return ProtocolContext(node, links, egp, self.node_name_id_mapping)

    @staticmethod
    def filter_for_id(node_id: str, dictionary: Dict[(str, str), any]) -> Dict[str, any]:
        keys = dictionary.keys()
        keys = filter(lambda key_tuple: key_tuple[0] == node_id or key_tuple[1] == node_id, keys)
        return {key[1]: dictionary[key] for key in keys}



class NetworkBuilder:

    @classmethod
    def build(cls, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Network:
        network = Network()

        network.nodes = NodeBuilder.build(config, hacky_is_squidasm_flag=hacky_is_squidasm_flag)

        ClassicalConnectionBuilder.build(config, network.nodes)

        network.links = LinkBuilder.build(config, network.nodes)

        network.egp = EGPBuilder.build(network)

        network.node_name_id_mapping = {node_id: node.ID for node_id, node in network.nodes.items()}

        return network


class NodeBuilder:

    @classmethod
    def build(cls, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Dict[str, ProcessingNode]:
        # TODO ProcessingNode is a very SquidASM centric object

        qdevice_nodes = {}
        for cfg in config.stacks:
            if cfg.qdevice_typ == "nv":
                qdevice_cfg = cfg.qdevice_cfg
                if not isinstance(qdevice_cfg, NVQDeviceConfig):
                    qdevice_cfg = NVQDeviceConfig(**cfg.qdevice_cfg)
                qdevice = build_nv_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            elif cfg.qdevice_typ == "generic":
                qdevice_cfg = cfg.qdevice_cfg
                if not isinstance(qdevice_cfg, GenericQDeviceConfig):
                    qdevice_cfg = GenericQDeviceConfig(**cfg.qdevice_cfg)
                qdevice = build_generic_qdevice(f"qdevice_{cfg.name}", cfg=qdevice_cfg)
            else:
                raise Exception("TODO")
            qdevice_nodes[cfg.name] = ProcessingNode(cfg.name, qdevice=qdevice, qdevice_type=cfg.qdevice_typ,
                                                     hacky_is_squidasm_flag=hacky_is_squidasm_flag)
        return qdevice_nodes


class ClassicalConnectionBuilder:
    @classmethod
    def build(cls, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode]):
        node_list = [nodes[key] for key in nodes.keys()]
        for s1, s2 in itertools.combinations(node_list, 2):
            s1.connect(s2)


class LinkBuilder:
    @classmethod
    def build(cls, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode])\
            -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}

        for link in config.links:
            node1 = nodes[link.stack1]
            node2 = nodes[link.stack2]
            if link.typ == "perfect":
                link_dist = PerfectStateMagicDistributor(
                    nodes=[node1, node2], state_delay=1000.0
                )
            elif link.typ == "depolarise":
                link_cfg = link.cfg
                if not isinstance(link_cfg, DepolariseLinkConfig):
                    link_cfg = DepolariseLinkConfig(**link.cfg)
                prob_max_mixed = fidelity_to_prob_max_mixed(link_cfg.fidelity)
                link_dist = DepolariseWithFailureMagicDistributor(
                    nodes=[node1, node2],
                    prob_max_mixed=prob_max_mixed,
                    prob_success=link_cfg.prob_success,
                    t_cycle=link_cfg.t_cycle,
                )
            elif link.typ == "nv":
                link_cfg = link.cfg
                if not isinstance(link_cfg, NVLinkConfig):
                    link_cfg = NVLinkConfig(**link.cfg)
                link_dist = NVSingleClickMagicDistributor(
                    nodes=[node1, node2],
                    length_A=link_cfg.length_A,
                    length_B=link_cfg.length_B,
                    full_cycle=link_cfg.full_cycle,
                    cycle_time=link_cfg.cycle_time,
                    alpha=link_cfg.alpha,
                )
            elif link.typ == "heralded":
                link_cfg = link.cfg
                if not isinstance(link_cfg, HeraldedLinkConfig):
                    link_cfg = HeraldedLinkConfig(**link.cfg)
                connection = MiddleHeraldedConnection(
                    name="heralded_conn", **link_cfg.dict()
                )
                link_dist = DoubleClickMagicDistributor(
                    [node1, node2], connection
                )
            else:
                raise ValueError

            link_prot = MagicLinkLayerProtocolWithSignaling(
                nodes=[node1, node2],
                magic_distributor=link_dist,
                translation_unit=SingleClickTranslationUnit(),
            )
            ProtocolController.register(link_prot)
            link_dict[(node1.name, node2.name)] = link_prot
            link_dict[(node2.name, node1.name)] = link_prot

        return link_dict


class EGPBuilder:

    @classmethod
    def build(cls, network: Network) -> Dict[(str, str), EgpProtocol]:

        egp_dict = {}
        for id_tuple, link_layer in network.links.items():
            node_id, peer_node_id = id_tuple
            node = network.nodes[node_id]
            egp = EgpProtocol(node, link_layer)
            egp_dict[(node_id, peer_node_id)] = egp
            ProtocolController.register(egp)
        return egp_dict


class ProtocolController:
    _registry = []

    @classmethod
    def register(cls, obj: object):
        assert callable(getattr(obj, "start", None))
        assert callable(getattr(obj, "stop", None))
        cls._registry.append(obj)

    @classmethod
    def start_all(cls):
        for obj in cls._registry:
            obj.start()

    @classmethod
    def stop_all(cls):
        for obj in cls._registry:
            obj.stop()
