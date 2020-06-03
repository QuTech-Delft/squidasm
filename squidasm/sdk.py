from netqasm.sdk import NetQASMConnection
from squidasm.queues import get_queue
from squidasm.backend import get_node_id, get_node_name


class NetSquidConnection(NetQASMConnection):

    def __init__(
        self,
        name,
        app_id=None,
        max_qubits=5,
        track_lines=False,
        app_dir=None,
        log_subroutines_dir=None,
        epr_sockets=None,
        compiler=None,
    ):
        self._message_queue = get_queue(name)
        super().__init__(
            name=name,
            app_id=app_id,
            max_qubits=max_qubits,
            track_lines=track_lines,
            app_dir=app_dir,
            log_subroutines_dir=log_subroutines_dir,
            epr_sockets=epr_sockets,
            compiler=compiler,
        )

    def _commit_message(self, msg, block=False):
        """Commit a message to the backend/qnodeos"""
        self._message_queue.put(msg)
        if block:
            self.block()

    def block(self):
        """Block until flushed subroutines finish"""
        self._message_queue.join()

    def _get_node_id(self, node_name):
        """Returns the node id for the node with the given name"""
        return get_node_id(name=node_name)

    def _get_node_name(self, node_id):
        """Returns the node name for the node with the given ID"""
        return get_node_name(node_id=node_id)
