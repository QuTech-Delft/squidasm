import netsquid as ns

from squidasm.network import BackendNetwork, create_network_stacks
from squidasm.qnodeos import SubroutineHandler
from squidasm.backend.glob import put_current_backend, pop_current_backend


class Backend:
    def __init__(self, node_names, node_ids=None, instr_log_dir=None, network_config=None, flavour=None):
        """Sets up the qmemories, nodes, connections and subroutine-handlers
        used to process NetQASM instructions.

        The Backend should be started by calling `start`, which also starts pydynaa.
        """
        network = BackendNetwork(node_names, network_config)
        self._nodes = network.nodes

        self._subroutine_handlers = self._get_subroutine_handlers(
            self._nodes,
            instr_log_dir=instr_log_dir,
            flavour=flavour
        )

        reaction_handlers = {node_name: self._subroutine_handlers[node_name].get_epr_reaction_handler()
                             for node_name in self._nodes}

        network_stacks = create_network_stacks(
            network=network,
            reaction_handlers=reaction_handlers,
        )
        for node_name in self._nodes.keys():
            network_stack = network_stacks[node_name]
            subroutine_handler = self._subroutine_handlers[node_name]
            subroutine_handler.network_stack = network_stack

    @property
    def nodes(self):
        return self._nodes

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
