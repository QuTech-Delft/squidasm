import netsquid as ns

from squidasm.network_setup import get_nodes
from squidasm.qnodeos import SubroutineHandler


class Backend:
    def __init__(self, node_names, num_qubits=5):
        """Sets up the qmemories, nodes, connections and subroutine-handlers
        used to process NetQASM instructions.

        The Backend should be started by calling `start`, which also starts pydynaa.
        """
        self._nodes = get_nodes(node_names, num_qubits=num_qubits)
        self._subroutine_handlers = self._get_subroutine_handlers(self._nodes)

    @staticmethod
    def _get_subroutine_handlers(nodes):
        subroutine_handlers = {}
        for node in nodes.values():
            subroutine_handler = SubroutineHandler(node)
            subroutine_handlers[node.name] = subroutine_handler
        return subroutine_handlers

    def start(self):
        """Starts the backend"""
        self._start_subroutine_handlers()
        ns.sim_run()

    def _start_subroutine_handlers(self):
        for subroutine_handler in self._subroutine_handlers.values():
            subroutine_handler.start()
