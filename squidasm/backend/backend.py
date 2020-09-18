from typing import List, Dict

import netsquid as ns
from netsquid.nodes import Node

from squidasm.qnodeos import SubroutineHandler
from squidasm.backend.glob import put_current_backend, pop_current_backend

from squidasm.network.network import NetSquidNetwork
from squidasm.network.config import default_network_config, parse_network_config, QuantumHardware
from squidasm.network.stack import NetworkStack
from squidasm.run.app_config import AppConfig

from netqasm.instructions.flavour import VanillaFlavour, NVFlavour


class Backend:
    def __init__(
        self,
        app_cfgs: List[AppConfig],
        instr_log_dir=None,
        network_config=None,
        flavour=None,
    ):
        """
        Sets up the network (containing nodes, qmemories and link layer services),
        as well as the subroutine handlers for each node on which an app runs.

        The Backend should be started by calling `start`, which also starts pydynaa.
        """

        # If no network_config specified, use a default one where nodes have the same names as the apps.
        if network_config is None:
            app_names = [cfg.app_name for cfg in app_cfgs]
            network_cfg_obj = default_network_config(app_names=app_names)
        else:
            network_cfg_obj = parse_network_config(cfg=network_config)

        # Create the network.
        network = NetSquidNetwork(
            network_config=network_cfg_obj,
            global_log_dir=instr_log_dir
        )
        self._network = network
        self._nodes = network.nodes

        self._app_node_map: Dict[str, Node] = dict()
        self._subroutine_handlers: Dict[str, SubroutineHandler] = dict()

        ll_services = network.link_layer_services

        # Create subroutine handlers for each app.
        for app in app_cfgs:
            try:
                node = network.get_node(app.node_name)
                self._app_node_map[app.app_name] = node
            except Exception:
                raise ValueError(
                    f"App {app.app_name} is supposed to run on node {app.node_name}"
                    f" but {app.node_name} does not exist in the network."
                )

            node_hardware = network.node_hardware_types[node.name]
            if node_hardware == QuantumHardware.NV:
                flavour = NVFlavour()
            else:
                flavour = VanillaFlavour()

            subroutine_handler = SubroutineHandler(
                node=node,
                instr_log_dir=instr_log_dir,
                flavour=flavour
            )
            subroutine_handler.network_stack = NetworkStack(
                node=node,
                link_layer_services=ll_services[node.name]
            )
            reaction_handler = subroutine_handler.get_epr_reaction_handler()
            for service in ll_services[node.name].values():
                service.add_reaction_handler(reaction_handler)

            self._subroutine_handlers[app.node_name] = subroutine_handler

    @property
    def nodes(self):
        return self._nodes

    @property
    def app_node_map(self):
        return self._app_node_map

    @property
    def subroutine_handlers(self):
        return self._subroutine_handlers

    @property
    def qmemories(self):
        return {node_name: node.qmemory for node_name, node in self.nodes.items()}

    @property
    def executioners(self):
        return {
            node_name: subroutine_handler._executioner
            for node_name, subroutine_handler in self.subroutine_handlers.items()
        }

    @staticmethod
    def _get_subroutine_handlers(nodes, instr_log_dir, flavour):
        subroutine_handlers = {}
        for node in nodes.values():
            subroutine_handler = SubroutineHandler(node, instr_log_dir=instr_log_dir, flavour=flavour)
            subroutine_handlers[node.name] = subroutine_handler
        return subroutine_handlers

    def start(self):
        """Starts the backend"""
        put_current_backend(self)
        self._start_subroutine_handlers()
        ns.sim_run()
        pop_current_backend()

    def _start_subroutine_handlers(self):
        for subroutine_handler in self._subroutine_handlers.values():
            subroutine_handler.start()
