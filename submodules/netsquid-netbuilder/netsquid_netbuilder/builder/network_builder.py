from __future__ import annotations

import heapq
from copy import copy
from typing import Dict, List, Type

from netsquid.components import Port
from netsquid_driver.classical_routing_service import ClassicalRoutingService
from netsquid_driver.classical_socket_service import (
    ClassicalSocket,
    ClassicalSocketService,
)
from netsquid_driver.driver import Driver
from netsquid_driver.EGP import EGPService
from netsquid_driver.entanglement_agreement_service import EntanglementAgreementService
from netsquid_driver.symmetric_agreement_service import SymmetricAgreementService
from netsquid_entanglementtracker.bell_state_tracker import BellStateTracker
from netsquid_entanglementtracker.entanglement_tracker_service import (
    EntanglementTrackerService,
)
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_magic.photonic_interface_interface import (
    IPhotonicInterfaceBuilder,
    IPhotonicInterfaceConfig,
)
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.builder.builder_utils import create_connection_ports
from netsquid_netbuilder.builder.metro_hub import HubBuilder, MetroHubNode
from netsquid_netbuilder.builder.repeater_chain import ChainBuilder
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceBuilder
from netsquid_netbuilder.modules.qrep_chain_control.interface import IQRepChainControlBuilder, IQRepChainControlConfig
from netsquid_netbuilder.modules.scheduler.interface import IScheduleBuilder
from netsquid_netbuilder.network import Network

from squidasm.sim.stack.egp import EgpProtocol
from squidasm.sim.stack.stack import ProcessingNode


class NetworkBuilder:
    def __init__(self):
        self.protocol_controller = ProtocolController()
        self.node_builder = NodeBuilder()
        self.clink_builder = ClassicalConnectionBuilder()
        self.link_builder = LinkBuilder(self.protocol_controller)
        self.routing_builder = NetworkServicesBuilder()
        self.socket_builder = ClassicalSocketBuilder(self.protocol_controller)
        self.egp_builder = EGPBuilder(self.protocol_controller)
        self.hub_builder = HubBuilder(self.protocol_controller)
        self.chain_builder = ChainBuilder(self.protocol_controller)
        self._logger = LogManager.get_stack_logger(self.__class__.__name__)

    def register_qdevice(self, key: str, builder: Type[IQDeviceBuilder]):
        self.node_builder.register(key, builder)
        self.chain_builder.register_qdevice(key, builder)

    def register_link(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builder.register(key, builder, config)
        self.hub_builder.register(key, builder, config)
        self.chain_builder.register_link(key, builder, config)

    def register_clink(
        self, key: str, builder: Type[ICLinkBuilder], config: Type[ICLinkConfig]
    ):
        self.clink_builder.register(key, builder, config)
        self.hub_builder.register_clink(key, builder, config)
        self.chain_builder.register_clink(key, builder, config)

    def register_scheduler(self, key: str, builder: Type[IScheduleBuilder]):
        self.hub_builder.register_scheduler(key, builder)

    def register_photonic_interface(
        self,
        key: str,
        builder: Type[IPhotonicInterfaceBuilder],
        config: Type[IPhotonicInterfaceConfig],
    ):
        self.chain_builder.register_photonic_interface(key, builder, config)

    def register_qrep_chain_control(
        self,
        key: str,
        builder: Type[IQRepChainControlBuilder],
        config: Type[IQRepChainControlConfig],
    ):
        self.chain_builder.register_qrep_chain_control(key, builder, config)

    def build(self, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Network:
        self.hub_builder.set_configs(config.hubs)
        self.chain_builder.set_configs(config.repeater_chains)

        # Create the data structures for the network
        network = Network()
        network.hubs = self.hub_builder.create_metro_hub_objects()
        network.chains = self.chain_builder.create_chain_objects(network.hubs)

        # Create node instances
        network.end_nodes = self.node_builder.build(config, hacky_is_squidasm_flag)
        self.hub_builder.register_end_nodes_to_hub(network)
        self.hub_builder.build_hub_nodes(network)
        self.chain_builder.build_repeater_nodes(network)

        # Set up a mapping between node name (str) and id (int)
        network.node_name_id_mapping = self.create_node_name_id_mapping(network)

        # Set up ports and connections for classical communication
        # black refactoring these lines makes it less readable
        # fmt: off
        network.ports = self.clink_builder.build(config, network)
        network.ports.update(self.hub_builder.build_classical_connections(network))
        network.ports.update(self.chain_builder.build_classical_connections(network))
        # fmt: on

        # Create instances of all direct quantum links
        network.links = self.link_builder.build(config, network.end_nodes)
        network.links.update(self.hub_builder.build_links(network))
        network.links.update(self.chain_builder.build_links(network))

        # Install photonic interface models in relevant links
        self.chain_builder.build_photonic_interfaces(network)

        # setup classical messaging
        self.routing_builder.build_routing_info(network)
        self.routing_builder.build_routing_service(network)
        self.routing_builder.build_entanglement_agreement_services(network)
        self.routing_builder.build_entanglement_tracker_services(network)
        network.sockets = self.socket_builder.build(network)

        # Create the scheduler
        self.hub_builder.build_schedule(network)

        # Set up EGP protocols
        network.egp = self.egp_builder.build(network)
        network.egp.update(self.chain_builder.build_egp(network))

        # "Move" the protocol controller to the network object
        for node in network.nodes.values():
            self.protocol_controller.register(node.driver)
        network._protocol_controller = self.protocol_controller

        self._logger.info(network.node_name_id_mapping)
        return network

    @staticmethod
    def create_node_name_id_mapping(network: Network) -> Dict[str, int]:
        mapping = {node_name: node.ID for node_name, node in network.end_nodes.items()}
        for chain in network.chains.values():
            mapping.update(
                {
                    node_name: node.ID
                    for node_name, node in chain.repeater_nodes_dict.items()
                }
            )
        return mapping


class NodeBuilder:
    def __init__(self):
        self.qdevice_builders: Dict[str, Type[IQDeviceBuilder]] = {}

    def register(self, key: str, builder: Type[IQDeviceBuilder]):
        self.qdevice_builders[key] = builder

    def build(
        self, config: StackNetworkConfig, hacky_is_squidasm_flag=True
    ) -> Dict[str, ProcessingNode]:
        nodes = {}
        for node_config in config.stacks:
            node_name = node_config.name
            node_qdevice_typ = node_config.qdevice_typ

            if node_qdevice_typ not in self.qdevice_builders.keys():
                # TODO improve exception
                raise Exception(f"No model of type: {node_qdevice_typ} registered")

            builder = self.qdevice_builders[node_qdevice_typ]
            qdevice = builder.build(
                f"qdevice_{node_name}", qdevice_cfg=node_config.qdevice_cfg
            )

            # TODO ProcessingNode is a very SquidASM centric object
            nodes[node_name] = ProcessingNode(
                node_name,
                qdevice=qdevice,
                qdevice_type=node_qdevice_typ,
                hacky_is_squidasm_flag=hacky_is_squidasm_flag,
            )
            self.qdevice_builders[node_qdevice_typ].build_services(nodes[node_name])
        return nodes


class ClassicalConnectionBuilder:
    def __init__(self):
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}
        self.clink_configs: Dict[str, Type[ICLinkConfig]] = {}

    def register(
        self, key: str, builder: Type[ICLinkBuilder], config: Type[ICLinkConfig]
    ):
        self.clink_builders[key] = builder
        self.clink_configs[key] = config

    def build(
        self, config: StackNetworkConfig, network: Network
    ) -> Dict[(str, str), Port]:
        nodes = network.end_nodes
        ports = {}
        if config.clinks is None:
            return {}
        for clink in config.clinks:
            s1 = nodes[clink.stack1]
            s2 = nodes[clink.stack2]
            clink_builder = self.clink_builders[clink.typ]
            connection = clink_builder.build(s1, s2, link_cfg=clink.cfg)

            ports.update(
                create_connection_ports(s1, s2, connection, port_prefix="external")
            )

        return ports


class LinkBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}
        self.link_configs: Dict[str, Type[ILinkConfig]] = {}

    def register(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builders[key] = builder
        self.link_configs[key] = config

    def build(
        self, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode]
    ) -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}
        if config.links is None:
            return {}
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

    def build(self, network: Network) -> Dict[(str, str), EGPService]:

        egp_dict = {}
        for id_tuple, link_layer in network.links.items():
            node_name, peer_node_name = id_tuple
            if (
                network.find_role(node_name) is network.Role.END_NODE
                and network.find_role(peer_node_name) is network.Role.END_NODE
            ):
                node = network.end_nodes[node_name]
                egp = EgpProtocol(node, link_layer)
                egp_dict[(node_name, peer_node_name)] = egp
                self.protocol_controller.register(egp)
        return egp_dict


class NetworkServicesBuilder:
    INSTANT_LINK_DELAY = 1e-9

    def __init__(self):
        self.routing_table: Dict[str, Dict[str, str]] = {}
        self.delays_table: Dict[(str, str), float] = {}
        self.routes: Dict[(str, str), List[str]] = {}
        self.graph: Dict[str, Dict[str, float]] = {}

    def _create_graph(self, network: Network):
        node_names = network.nodes.keys()
        self.graph = {node_name: {} for node_name in node_names}
        for (node_name, peer_name), port in network.ports.items():
            self.graph[node_name][peer_name] = self._find_delay(port)

    @staticmethod
    def _find_delay(port: Port) -> float:
        connection = port.connected_port.component
        channel_a_to_b = connection.subcomponents["channel_AtoB"]
        return channel_a_to_b.compute_delay()

    def _calculate_local_routing_table(
        self, node_name
    ) -> (Dict[str, float], Dict[str, List[str]]):
        distances = {node: float("inf") for node in self.graph.keys()}
        routes = {node: [] for node in self.graph.keys()}
        distances[node_name] = 0
        routes[node_name] = [node_name]
        priority_queue = [(0.0, node_name)]

        while priority_queue:
            current_dist, current_node = heapq.heappop(priority_queue)

            if current_dist > distances[current_node]:
                continue

            for node, link_dist in self.graph[current_node].items():
                dist = current_dist + link_dist
                if dist < distances[node] or (
                    dist == distances[node]
                    and len(routes[current_node]) + 1 < len(routes[node])
                ):
                    distances[node] = dist
                    routes[node] = copy(routes[current_node])
                    routes[node].append(node)
                    heapq.heappush(priority_queue, (dist, node))

        for _, rout in routes.items():
            # TODO Can crash if no route found to node
            rout.remove(node_name)

        return distances, routes

    def _calculate_routing_tables(self, network: Network):
        for node_name in network.nodes.keys():
            distances, routes = self._calculate_local_routing_table(node_name)
            self.routing_table[node_name] = {}
            for remote_node in network.nodes.keys():
                if remote_node == node_name:
                    continue
                self.delays_table[(node_name, remote_node)] = distances[remote_node]
                self.routes[(node_name, remote_node)] = routes[remote_node]
                self.routing_table[node_name][remote_node] = routes[remote_node][0]

    def build_routing_info(self, network):
        self._create_graph(network)
        self._calculate_routing_tables(network)

    def build_routing_service(self, network: Network):
        for node in network.nodes.values():
            assert isinstance(node, ProcessingNode) or isinstance(node, MetroHubNode)
            local_routing_table = self.routing_table[node.name]
            local_port_routing_table = {
                target_name: network.ports[(node.name, forward_node_name)]
                for target_name, forward_node_name in local_routing_table.items()
            }
            routing_service = ClassicalRoutingService(
                node=node, forwarding_table=local_port_routing_table
            )

            node.driver.add_service(ClassicalRoutingService, routing_service)
            external_ports = Network.filter_for_node(node.name, network.ports)
            routing_service.register_ports(
                [port.name for port in external_ports.values()]
            )

    def build_entanglement_agreement_services(self, network: Network):
        for node in network.nodes.values():
            assert isinstance(node, ProcessingNode) or isinstance(node, MetroHubNode)

            node.driver.add_service(
                EntanglementAgreementService,
                SymmetricAgreementService(
                    node=node,
                    delay_per_node=Network.filter_for_node(
                        node.name, self.delays_table
                    ),
                ),
            )

    def build_entanglement_tracker_services(self, network: Network):
        for node in network.nodes.values():
            assert isinstance(node, ProcessingNode) or isinstance(node, MetroHubNode)
            node.driver.add_service(EntanglementTrackerService, BellStateTracker(node))


class ClassicalSocketBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller

    def build(self, network: Network) -> Dict[(str, str), ClassicalSocket]:
        sockets = {}
        for node in network.end_nodes.values():
            service = ClassicalSocketService(node=node)
            node.driver.add_service(ClassicalSocketService, service)
            for remote_node in network.end_nodes.values():
                if remote_node is node:
                    continue

                socket = ClassicalSocket(
                    socket_service=service,
                    remote_node_name=remote_node.name,
                    app_name="root",
                    remote_app_name="root",
                )
                sockets[(node.name, remote_node.name)] = socket
                self.protocol_controller.register(socket)

        return sockets


class ProtocolController:
    def __init__(self):
        self._registry = []
        self._drivers = []

    def register(self, obj: object):
        if isinstance(obj, Driver):
            self._drivers.append(obj)
            return
        assert callable(getattr(obj, "start", None))
        assert callable(getattr(obj, "stop", None))
        self._registry.append(obj)

    def start_all(self):
        for obj in self._registry:
            obj.start()
        for driver in self._drivers:
            driver.start_all_services()

    def stop_all(self):
        for obj in self._registry:
            obj.stop()
        for driver in self._drivers:
            driver.stop_all_services()
