import netsquid as ns

from squidasm.network_setup import get_nodes
from squidasm.qnodeos import SubroutineHandler
from squidasm.network_stack import setup_network_stacks


_CURRENT_BACKEND = [None]


def get_running_backend(block=True):
    while True:
        backend = _CURRENT_BACKEND[0]
        if backend is not None:
            return backend
        if not block:
            return None


def get_current_nodes(block=True):
    backend = get_running_backend(block=block)
    return backend.nodes


def get_current_node_names(block=True):
    backend = get_running_backend(block=block)
    return backend.nodes.keys()


def get_current_node_ids(block=True):
    backend = get_running_backend(block=block)
    return {node_name: node.ID for node_name, node in backend.nodes.items()}


class Backend:
    def __init__(self, node_names, node_ids=None, num_qubits=5):
        """Sets up the qmemories, nodes, connections and subroutine-handlers
        used to process NetQASM instructions.

        The Backend should be started by calling `start`, which also starts pydynaa.
        """
        self._nodes = get_nodes(node_names, node_ids=node_ids, num_qubits=num_qubits)
        self._subroutine_handlers = self._get_subroutine_handlers(self._nodes)
        reaction_handlers = {node_name: self._subroutine_handlers[node_name].get_epr_reaction_handler()
                             for node_name in self._nodes}
        network_stacks = setup_network_stacks(nodes=self._nodes, reaction_handlers=reaction_handlers)
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

    @staticmethod
    def _get_subroutine_handlers(nodes):
        subroutine_handlers = {}
        for node in nodes.values():
            subroutine_handler = SubroutineHandler(node)
            subroutine_handlers[node.name] = subroutine_handler
        return subroutine_handlers

    def start(self):
        """Starts the backend"""
        _put_current_backend(self)
        self._start_subroutine_handlers()
        ns.sim_run()
        _pop_current_backend()

    def _start_subroutine_handlers(self):
        for subroutine_handler in self._subroutine_handlers.values():
            subroutine_handler.start()


def _put_current_backend(backend):
    if _CURRENT_BACKEND[0] is not None:
        raise RuntimeError("Already a backend running")
    else:
        _CURRENT_BACKEND[0] = backend


def _pop_current_backend():
    _CURRENT_BACKEND[0] = None
