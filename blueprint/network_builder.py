from __future__ import annotations

import itertools
from typing import Dict, List, Type

from netsquid.components import Port

from blueprint.base_configs import StackNetworkConfig

from blueprint.links.interface import ILinkBuilder
from blueprint.clinks.interface import ICLinkBuilder
from blueprint.network import Network

from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from blueprint.clinks.default import DefaultCLinkBuilder
from blueprint.clinks.instant import InstantCLinkBuilder

from squidasm.sim.stack.stack import NodeStack, StackNetwork, ProcessingNode
from squidasm.sim.stack.egp import EgpProtocol
from blueprint.qdevices.interface import IQDeviceBuilder
from blueprint.qdevices.generic import GenericQDeviceBuilder
from blueprint.qdevices.nv import NVQDeviceBuilder
from blueprint.links.nv import NVLinkBuilder
from blueprint.links.perfect import PerfectLinkBuilder
from blueprint.links.heralded import HeraldedLinkBuilder
from blueprint.links.depolarise import DepolariseLinkBuilder
from blueprint.scheduler.interface import IScheduleProtocol, IScheduleBuilder
from blueprint.scheduler.instant import InstantScheduleBuilder


class NetworkBuilder:
    def __init__(self):
        self.protocol_controller = ProtocolController()
        self.node_builder = NodeBuilder()
        self.classical_connection_builder = ClassicalConnectionBuilder()
        self.link_builder = LinkBuilder(self.protocol_controller)
        self.egp_builder = EGPBuilder(self.protocol_controller)
        self.schedule_builder = ScheduleBuilder(self.protocol_controller)

        # Default qdevice models registration
        self.node_builder.register_model("generic", GenericQDeviceBuilder)
        self.node_builder.register_model("nv", NVQDeviceBuilder)

        # default link models registration
        self.link_builder.register("perfect", PerfectLinkBuilder)
        self.link_builder.register("depolarise", DepolariseLinkBuilder)
        self.link_builder.register("heralded", HeraldedLinkBuilder)
        self.link_builder.register("nv", NVLinkBuilder)

        # default clink models registration
        self.classical_connection_builder.register_model("instant", InstantCLinkBuilder)
        self.classical_connection_builder.register_model("default", DefaultCLinkBuilder)

    def build(self, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Network:
        network = Network()

        network.nodes = self.node_builder.build(config, hacky_is_squidasm_flag=hacky_is_squidasm_flag)

        self.classical_connection_builder.build(config, network, hacky_is_squidasm_flag=hacky_is_squidasm_flag)

        network.links = self.link_builder.build(config, network.nodes)

        network.schedulers = self.schedule_builder.build(network)

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
    def __init__(self):
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}

    def register_model(self, key: str, builder: Type[ICLinkBuilder]):
        self.clink_builders[key] = builder

    def build(self, config: StackNetworkConfig, network: Network, hacky_is_squidasm_flag):
        nodes = network.nodes
        node_list = [nodes[key] for key in nodes.keys()]
        for clink in config.clinks:
            s1 = nodes[clink.stack1]
            s2 = nodes[clink.stack2]
            clink_builder = self.clink_builders[clink.typ]
            connection = clink_builder.build(s1, s2, link_cfg=clink.cfg)

            s1_port: Port = s1.add_ports([f"host_{s2.ID}"])[0]
            s2_port: Port = s2.add_ports([f"host_{s1.ID}"])[0]

            # link
            s1_port.connect(connection.port_A)
            s2_port.connect(connection.port_B)

            network.ports[(s1.name, s2.name)] = s1_port
            network.ports[(s2.name, s1.name)] = s2_port

            if hacky_is_squidasm_flag:
                s1.register_peer(s2.ID)
                s2.register_peer(s1.ID)
                connection_qnos = clink_builder.build(s1, s2, link_cfg=clink.cfg)

                s1.qnos_peer_port(s2.ID).connect(connection_qnos.port_A)
                s2.qnos_peer_port(s1.ID).connect(connection_qnos.port_B)


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


class ScheduleBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller

    def build(self, network: Network) -> Dict[str, IScheduleProtocol]:
        # TODO currently hard coded InstantScheduler, make open
        schedulers = InstantScheduleBuilder.build(network)
        for scheduler in schedulers.values():
            self.protocol_controller.register(scheduler)
        return schedulers


class EGPBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller

    def build(self, network: Network) -> Dict[(str, str), EgpProtocol]:

        egp_dict = {}
        for id_tuple, link_layer in network.links.items():
            node_name, peer_node_id = id_tuple
            node = network.nodes[node_name]
            egp = EgpProtocol(node, link_layer, network.schedulers[node_name])
            egp_dict[(node_name, peer_node_id)] = egp
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
