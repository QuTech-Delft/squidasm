from netsquid_magic.link_layer import LinkLayerOKTypeK
from netqasm.sdk import NetQASMConnection, ThreadSocket
from squidasm.queues import get_queue, Signal
from squidasm.backend import get_node_id, get_node_name
from squidasm.messages import Message, InitNewAppMessage, MessageType


class NetSquidConnection(NetQASMConnection):

    # Class to use to pack entanglement information
    # TODO how to handle other types?
    ENT_INFO = LinkLayerOKTypeK

    def __init__(self, name, app_id=None, max_qubits=5, track_lines=False, log_subroutines_dir=None):
        self._message_queue = get_queue(name)
        super().__init__(
            name=name,
            app_id=app_id,
            max_qubits=max_qubits,
            track_lines=track_lines,
            log_subroutines_dir=log_subroutines_dir,
        )

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._message_queue.put(Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=self._appID,
                max_qubits=max_qubits,
            ),
        ))

    def commit(self, subroutine, block=True):
        self._submit_subroutine(subroutine, block=block)

    def block(self):
        """Block until flushed subroutines finish"""
        self._message_queue.join()

    def close(self, release_qubits=True):
        super().close(release_qubits=release_qubits)
        self._signal_stop()

    def _submit_subroutine(self, subroutine, block=True):
        self._logger.debug(f"Puts the next subroutine:\n{subroutine}")
        self._message_queue.put(Message(type=MessageType.SUBROUTINE, msg=subroutine))
        if block:
            self._message_queue.join()

    def _signal_stop(self):
        self._message_queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))

    def _get_remote_node_id(self, name):
        return get_node_id(name=name)

    def _get_remote_node_name(self, node_id):
        return get_node_name(node_id=node_id)


class NetSquidSocket(ThreadSocket):
    def __init__(self, node_name, remote_node_name, socket_id=0, timeout=None,
                 use_callbacks=False):
        node_id = get_node_id(node_name)
        remote_node_id = get_node_id(remote_node_name)
        super().__init__(
            node_id=node_id,
            remote_node_id=remote_node_id,
            socket_id=socket_id,
            timeout=timeout,
            use_callbacks=use_callbacks,
        )
