# from time import sleep
from collections import defaultdict
from timeit import default_timer as timer

from netsquid_magic.link_layer import (
    LinkLayerService,
    MagicLinkLayerProtocol,
    SingleClickTranslationUnit,
    LinkLayerRecv,
)
from netsquid_magic.sleeper import Sleeper
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor

from netqasm.network_stack import BaseNetworkStack


class NetworkStack(BaseNetworkStack):
    def __init__(self, node, link_layer_services):
        self._node = node
        self._link_layer_services = link_layer_services

        self._sleeper = Sleeper()

    def put(self, request):
        remote_node_id = request.remote_node_id
        link_layer_service = self._link_layer_services.get(remote_node_id)
        if link_layer_service is None:
            raise ValueError(f"The node with ID {remote_node_id} is not known to the network")
        return link_layer_service.put(request)

    def setup_circuits(self, circuit_rules=None, timeout=1):
        if circuit_rules is None:
            return
        self._setup_recv_rules(recv_rules=circuit_rules.recv_rules)
        # Wait until other nodes have setup correct recv rules that this one needs
        yield from self._wait_for_circuits(create_rules=circuit_rules.create_rules, timeout=timeout)

    def _setup_recv_rules(self, recv_rules):
        for recv_rule in recv_rules:
            recv_request = self._get_recv_request(
                remote_node_id=recv_rule.remote_node_id,
                purpose_id=recv_rule.purpose_id,
            )
            self.put(request=recv_request)

    def _get_recv_request(self, remote_node_id, purpose_id):
        return LinkLayerRecv(
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
        )

    def _wait_for_circuits(self, create_rules, timeout=1):
        t_start = timer()
        for create_rule in create_rules:
            while True:
                if self._has_rule(rule=create_rule):
                    break
                # Wait a little until checking again
                yield self._sleeper.sleep()
                now = timer()
                if (now - t_start) > timeout:
                    raise TimeoutError("Remote node did not initialize the correct rules")

    def _has_rule(self, rule):
        # NOTE the magic snippet doesn't use the Rule class so use a tuple
        remote_rule = self._node.ID, rule.purpose_id
        # TODO this is a hacky way to get whether the rule is set for now
        # should be changed to have a proper way to do this without calling private methods
        link_layer_service = self._link_layer_services[rule.remote_node_id]
        magic_protocol = link_layer_service._magic_protocol
        return remote_rule in magic_protocol._recv_rules[rule.remote_node_id]


def setup_link_layer_services(nodes, reaction_handlers, network_config=None):
    node_names = list(nodes.keys())
    link_layer_services = defaultdict(dict)
    for i, node_name1 in enumerate(node_names):
        for j in range(i + 1, len(node_names)):
            node_name2 = node_names[j]
            node_pair = [nodes[node_name1], nodes[node_name2]]
            magic_protocol = setup_magic_link_layer_protocol(node_pair=node_pair, network_config=network_config)
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


def setup_magic_link_layer_protocol(node_pair, network_config=None):
    # TODO use network config for setting up magic distributor
    magic_distributor = PerfectStateMagicDistributor(node_pair, state_delay=1)
    translation_unit = SingleClickTranslationUnit()
    magic_protocol = MagicLinkLayerProtocol(
        nodes=node_pair,
        magic_distributor=magic_distributor,
        translation_unit=translation_unit,
    )

    return magic_protocol


def setup_network_stacks(nodes, reaction_handlers, network_config=None):
    link_layer_services = setup_link_layer_services(nodes, reaction_handlers, network_config=network_config)
    network_stacks = {}
    for node_name, node in nodes.items():
        network_stack = NetworkStack(node=node, link_layer_services=link_layer_services[node_name])
        network_stacks[node_name] = network_stack

    return network_stacks
