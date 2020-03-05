from collections import defaultdict

from netsquid_magic.link_layer import LinkLayerService, MagicLinkLayerProtocol, SingleClickTranslationUnit
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor

from netqasm.network_stack import BaseNetworkStack


class NetworkStack(BaseNetworkStack):
    def __init__(self, node, link_layer_services):
        self._node = node
        self._link_layer_services = link_layer_services

    def put(self, remote_node_id, request):
        link_layer_service = self._link_layer_services.get(remote_node_id)
        if link_layer_service is None:
            raise ValueError(f"The node with ID {remote_node_id} is not known to the network")
        return link_layer_service.put(request)


def setup_link_layer_services(nodes, reaction_handlers):
    node_names = list(nodes.keys())
    link_layer_services = defaultdict(dict)
    for i, node_name1 in enumerate(node_names):
        for j in range(i + 1, len(node_names)):
            node_name2 = node_names[j]
            node_pair = [nodes[node_name1], nodes[node_name2]]
            magic_protocol = setup_magic_link_layer_protocol(node_pair=node_pair)
            for node, remote_node in [node_pair, reversed(node_pair)]:
                reaction_handler = reaction_handlers[node.name]
                link_layer_service = LinkLayerService(
                    node=node,
                    magic=True,
                    magic_protocol=magic_protocol,
                    reaction_handler=reaction_handler,
                )
                link_layer_services[node.name][remote_node.ID] = link_layer_service

    return link_layer_services


def setup_magic_link_layer_protocol(node_pair):
    magic_distributor = PerfectStateMagicDistributor(node_pair, state_delay=1)
    translation_unit = SingleClickTranslationUnit()
    magic_protocol = MagicLinkLayerProtocol(
        nodes=node_pair,
        magic_distributor=magic_distributor,
        translation_unit=translation_unit,
    )

    return magic_protocol


def setup_network_stacks(nodes, reaction_handlers):
    link_layer_services = setup_link_layer_services(nodes, reaction_handlers)
    network_stacks = {}
    for node_name, node in nodes.items():
        network_stack = NetworkStack(node=node, link_layer_services=link_layer_services[node_name])
        network_stacks[node_name] = network_stack

    return network_stacks
