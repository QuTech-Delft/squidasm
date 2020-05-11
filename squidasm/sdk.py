from netsquid_magic.link_layer import LinkLayerOKTypeK
from netqasm.sdk import NetQASMConnection, ThreadSocket
from netqasm.network_stack import CircuitRules, Rule
from squidasm.queues import get_queue, Signal
from squidasm.backend import get_node_id, get_node_name
from squidasm.messages import Message, InitNewAppMessage, MessageType, StopAppMessage


class NetSquidConnection(NetQASMConnection):

    # Class to use to pack entanglement information
    # TODO how to handle other types?
    ENT_INFO = LinkLayerOKTypeK

    def __init__(
        self,
        name,
        app_id=None,
        max_qubits=5,
        track_lines=False,
        log_subroutines_dir=None,
        epr_to=None,
        epr_from=None,
        compiler=None,
    ):
        self._message_queue = get_queue(name)
        super().__init__(
            name=name,
            app_id=app_id,
            max_qubits=max_qubits,
            track_lines=track_lines,
            log_subroutines_dir=log_subroutines_dir,
            epr_to=epr_to,
            epr_from=epr_from,
            compiler=compiler,
        )

    def _init_new_app(self, max_qubits, circuit_rules=None):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._message_queue.put(Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=self._appID,
                max_qubits=max_qubits,
                circuit_rules=circuit_rules,
            ),
        ))

    def _get_circuit_rules(self, epr_to=None, epr_from=None):
        create_rules = get_rules(rule_spec=epr_to)
        recv_rules = get_rules(rule_spec=epr_from)
        return CircuitRules(create_rules=create_rules, recv_rules=recv_rules)

    def commit(self, subroutine, block=True):
        self._submit_subroutine(subroutine, block=block)

    def block(self):
        """Block until flushed subroutines finish"""
        self._message_queue.join()

    def _submit_subroutine(self, subroutine, block=True):
        self._logger.debug(f"Puts the next subroutine:\n{subroutine}")
        self._message_queue.put(Message(type=MessageType.SUBROUTINE, msg=subroutine))
        if block:
            self._message_queue.join()

    def _signal_stop(self, stop_backend=True):
        self._message_queue.put(Message(
            type=MessageType.STOP_APP,
            msg=StopAppMessage(app_id=self._appID),
        ))

        if stop_backend:
            self._message_queue.put(Message(
                type=MessageType.SIGNAL,
                msg=Signal.STOP,
            ))

    def _get_remote_node_id(self, name):
        return get_node_id(name=name)

    def _get_remote_node_name(self, node_id):
        return get_node_name(node_id=node_id)


def get_rules(rule_spec=None):
    """Get ciruit rules form specification"""
    if rule_spec is None:
        return []
    if isinstance(rule_spec, str) or isinstance(rule_spec, int):
        return get_rules(rule_spec=[(rule_spec, 0)])  # Default to purpose ID 0
    if isinstance(rule_spec, tuple):
        return get_rules(rule_spec=[rule_spec])

    if not isinstance(rule_spec, list):
        raise TypeError(f"Rules specification should be a list, not {type(rule_spec)}")
    rules = []
    for rule in rule_spec:
        if not (isinstance(rule, tuple) and len(rule) == 2):
            raise TypeError(f"A rule should be a tuple of length 2, not {len(rule)} as for {rule}")
        remote_node, purpose_id = rule
        remote_node_id = _parse_remote_node_id(remote_node)
        rules.append(Rule(remote_node_id=remote_node_id, purpose_id=purpose_id))
    return rules


def _parse_remote_node_id(remote_node):
    if isinstance(remote_node, str):
        remote_node_id = get_node_id(name=remote_node)
    elif isinstance(remote_node, int):
        remote_node_id = remote_node
    else:
        raise TypeError(f"Remote node specification should be str (name) or int (ID), not {type(remote_node)}")
    return remote_node_id


class NetSquidSocket(ThreadSocket):
    def __init__(
        self,
        node_name,
        remote_node_name,
        socket_id=0,
        timeout=None,
        use_callbacks=False,
    ):
        """Same as :class:`netqasm.classical_communication.thread_socket.socket.ThreadSocket`
        but using node names instead of IDs"""
        self._node_name = node_name
        self._remote_node_name = remote_node_name
        node_id = get_node_id(self.node_name)
        remote_node_id = get_node_id(self.remote_node_name)
        super().__init__(
            node_id=node_id,
            remote_node_id=remote_node_id,
            socket_id=socket_id,
            timeout=timeout,
            use_callbacks=use_callbacks,
        )

    @property
    def node_name(self):
        return self._node_name

    @property
    def remote_node_name(self):
        return self._remote_node_name

    @property
    def key(self):
        return self.node_name, self.remote_node_name, self.id

    @property
    def remote_key(self):
        return self.remote_node_name, self.node_name, self.id
