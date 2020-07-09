from netqasm.parsing import parse_text_subroutine
from netqasm.logging import get_netqasm_logger
from netqasm.messages import Message, InitNewAppMessage, MessageType, OpenEPRSocketMessage
from squidasm.queues import get_queue, Signal
from squidasm.backend import get_node_id, get_node_name


class SimpleCommunicator:
    def __init__(self, node_name, subroutines, app_id=0, max_qubits=5, epr_sockets=None):
        if isinstance(subroutines, str):
            subroutines = [subroutines]
        self._subroutines = [parse_text_subroutine(subroutine) for subroutine in subroutines]
        self._node_name = node_name
        self._message_queue = get_queue(node_name)
        self._init_new_app(app_id=app_id, max_qubits=max_qubits)
        self._setup_epr_sockets(epr_sockets=epr_sockets)

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self._node_name})")

    def _commit_message(self, msg, block=False):
        """Commit a message to the backend/qnodeos"""
        self._message_queue.put(msg)
        if block:
            self.block()

    def block(self):
        """Block until flushed subroutines finish"""
        self._message_queue.join()

    def _init_new_app(self, app_id, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._commit_message(msg=Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=app_id,
                max_qubits=max_qubits,
            ),
        ))

    def _setup_epr_sockets(self, epr_sockets):
        if epr_sockets is None:
            return
        for epr_socket in epr_sockets:
            epr_socket.conn = self
            self._setup_epr_socket(
                epr_socket_id=epr_socket._epr_socket_id,
                remote_node_id=epr_socket._remote_node_id,
                remote_epr_socket_id=epr_socket._remote_epr_socket_id,
            )

    def _setup_epr_socket(self, epr_socket_id, remote_node_id, remote_epr_socket_id):
        """Sets up a new epr socket"""
        self._commit_message(msg=Message(
            type=MessageType.OPEN_EPR_SOCKET,
            msg=OpenEPRSocketMessage(
                epr_socket_id=epr_socket_id,
                remote_node_id=remote_node_id,
                remote_epr_socket_id=remote_epr_socket_id,
            ),
        ))

    def _get_node_id(self, node_name):
        """Returns the node id for the node with the given name"""
        return get_node_id(name=node_name)

    def _get_node_name(self, node_id):
        """Returns the node name for the node with the given ID"""
        return get_node_name(node_id=node_id)

    def run(self, num_times=1):
        for _ in range(num_times):
            for subroutine in self._subroutines:
                self._submit_subroutine(subroutine=subroutine)
        # Wait for everything to finish before stopping
        self.block()
        self._signal_stop()

    def _submit_subroutine(self, subroutine):
        self._logger.debug(f"SimpleCommunicator for node {self._node_name} puts the next subroutine:\n"
                           f"{subroutine}")
        self._commit_message(msg=Message(type=MessageType.SUBROUTINE, msg=bytes(subroutine)))

    def _signal_stop(self):
        self._commit_message(msg=Message(type=MessageType.SIGNAL, msg=Signal.STOP), block=True)
