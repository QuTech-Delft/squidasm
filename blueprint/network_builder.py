from __future__ import annotations

import itertools
from typing import Dict, List, Type

from blueprint.base_configs import StackNetworkConfig
from blueprint.links import (
    DepolariseLinkConfig,
    HeraldedLinkConfig,
    NVLinkConfig,
)
from blueprint.links.interface import ILinkBuilder
from blueprint.network import Network

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
from blueprint.qdevices.interface import IQDeviceBuilder
from blueprint.qdevices.generic import GenericQDeviceBuilder
from blueprint.qdevices.nv import NVQDeviceBuilder
from blueprint.links.nv import NVLinkBuilder
from blueprint.links.perfect import PerfectLinkBuilder
from blueprint.links.heralded import HeraldedLinkBuilder
from blueprint.links.depolarise import DepolariseLinkBuilder



class NetworkBuilder:
    def __init__(self):
        self.protocol_controller = ProtocolController()
        self.node_builder = NodeBuilder()
        self.classical_connection_builder = ClassicalConnectionBuilder()
        self.link_builder = LinkBuilder(self.protocol_controller)
        self.egp_builder = EGPBuilder(self.protocol_controller)

        # Default qdevice models registration
        self.node_builder.register_model("generic", GenericQDeviceBuilder)
        self.node_builder.register_model("nv", NVQDeviceBuilder)

        # default link models registration
        self.link_builder.register("perfect", PerfectLinkBuilder)
        self.link_builder.register("depolarise", DepolariseLinkBuilder)
        self.link_builder.register("heralded", HeraldedLinkBuilder)
        self.link_builder.register("nv", NVLinkBuilder)

    def build(self, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Network:
        network = Network()

        network.nodes = self.node_builder.build(config, hacky_is_squidasm_flag=hacky_is_squidasm_flag)

        self.classical_connection_builder.build(config, network.nodes)

        network.links = self.link_builder.build(config, network.nodes)

        network.egp = self.egp_builder.build(network)

        network.node_name_id_mapping = {node_id: node.ID for node_id, node in network.nodes.items()}

        return network


class NodeBuilder:
    def __init__(self):
        self.qdevice_builders: Dict[str, Type[IQDeviceBuilder]] = {}

    def register_model(self, key: str, builder: Type[IQDeviceBuilder]):
        self.qdevice_builders[key] = builder

    def build(self, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Dict[str, ProcessingNode]:
        nodes = {}
        for node_config in config.stacks:
            if node_config.qdevice_typ not in self.qdevice_builders.keys():
                # TODO improve exception
                raise Exception(f"No model of type: {node_config.qdevice_typ} registered")

            builder = self.qdevice_builders[node_config.qdevice_typ]
            qdevice = builder.build(f"qdevice_{node_config.name}",
                                    qdevice_cfg=node_config.qdevice_cfg)

            # TODO ProcessingNode is a very SquidASM centric object
            nodes[node_config.name] = ProcessingNode(node_config.name,
                                                     qdevice=qdevice, qdevice_type=node_config.qdevice_typ,
                                                     hacky_is_squidasm_flag=hacky_is_squidasm_flag)
        return nodes


class ClassicalConnectionBuilder:
    def build(self, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode]):
        node_list = [nodes[key] for key in nodes.keys()]
        for s1, s2 in itertools.combinations(node_list, 2):
            s1.connect(s2)


class LinkBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}

    def register(self, key: str, builder: Type[ILinkBuilder]):
        self.link_builders[key] = builder

    def build(self, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode])\
            -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}

        for link in config.links:
            node1 = nodes[link.stack1]
            node2 = nodes[link.stack2]
            if link.typ not in self.link_builders.keys():
                # TODO improve exception
                raise Exception(f"No model of type: {link.typ} registered")

            builder = self.link_builders[link.typ]
            link_prot = builder.build(node1, node2, link.cfg)
            self.protocol_controller.register(link_prot)
            link_dict[(node1.name, node2.name)] = link_prot
            link_dict[(node2.name, node1.name)] = link_prot

        return link_dict


class EGPBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller

    def build(self, network: Network) -> Dict[(str, str), EgpProtocol]:

        egp_dict = {}
        for id_tuple, link_layer in network.links.items():
            node_id, peer_node_id = id_tuple
            node = network.nodes[node_id]
            egp = EgpProtocol(node, link_layer)
            egp_dict[(node_id, peer_node_id)] = egp
            self.protocol_controller.register(egp)
        return egp_dict


class ProtocolController:
    def __init__(self):
        self._registry = []

    def register(self, obj: object):
        assert callable(getattr(obj, "start", None))
        assert callable(getattr(obj, "stop", None))
        self._registry.append(obj)

    def start_all(self):
        for obj in self._registry:
            obj.start()

    def stop_all(self):
        for obj in self._registry:
            obj.stop()
