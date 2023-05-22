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


class Network:
    def __init__(self):
        self.nodes: Dict[str, ProcessingNode] = {}
        self.links: Dict[(str, str), MagicLinkLayerProtocolWithSignaling] = {}
        self.egp: Dict[(str, str), EgpProtocol] = {}

    # def get_links(self, node_id: str) -> List[MagicLinkLayerProtocol]:
    #     keys = self.links.keys()
    #     keys = filter(lambda key_tuple: key_tuple[0] == node_id or key_tuple[1] == node_id, keys)
    #     return [self.links[key] for key in keys]



class NetworkBuilder:

    @classmethod
    def build(cls, config: StackNetworkConfig) -> Network:
        network = Network()


        return network


class NodeBuilder:

    @classmethod
    def build(cls, config: StackNetworkConfig) -> List[ProcessingNode]:
        # TODO ProcessingNode is a very SquidASM centric object

        qdevice_nodes = []
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
            qdevice_nodes.append(ProcessingNode(cfg.name, qdevice=qdevice, qdevice_type=cfg.qdevice_typ))
        return qdevice_nodes


class ClassicalConnectionBuilder:
    @classmethod
    def build(cls, config: StackNetworkConfig, nodes: List[ProcessingNode]):
        for s1, s2 in itertools.combinations(nodes, 2):
            s1.connect(s2)


class LinkBuilder:
    @classmethod
    def build(cls, config: StackNetworkConfig, nodes: List[ProcessingNode])\
            -> Dict[str, List[(str, MagicLinkLayerProtocolWithSignaling)]]:
        node_dict = {node.name: node for node in nodes}
        link_dict = {node.name: [] for node in nodes}

        for link in config.links:
            node1 = node_dict[link.stack1]
            node2 = node_dict[link.stack2]
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
            link_dict[node1.name].append((node2.name, link_prot))
            link_dict[node2.name].append((node1.name, link_prot))

        return link_dict


class EGPBuilder:

    @classmethod
    def build(cls, node: ProcessingNode, links: Dict[str, (str, MagicLinkLayerProtocolWithSignaling)]) -> Dict[str, EgpProtocol]:
        if node.name not in links.keys():
            raise Exception("TODO")
        peer_egp_dict = {}
        for peer, link_layer in links[node.name]:
            egp = EgpProtocol(node, link_layer)
            peer_egp_dict[peer] = egp
        return peer_egp_dict


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
