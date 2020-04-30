# from time import sleep
from queue import Empty
from types import GeneratorType

from netsquid.protocols import NodeProtocol
from netsquid_magic.sleeper import Sleeper

from netqasm.parsing import parse_binary_subroutine
from netqasm.logging import get_netqasm_logger
from squidasm.messages import MessageType
from squidasm.executioner import NetSquidExecutioner
from squidasm.queues import get_queue, Signal


class SubroutineHandler(NodeProtocol):
    def __init__(self, node, instr_log_dir=None):
        super().__init__(node=node)
        self._executioner = NetSquidExecutioner(node=node, instr_log_dir=instr_log_dir)

        self._message_queue = get_queue(self.node.name)

        self._message_handlers = self._get_message_handlers()

        self._sleeper = Sleeper()

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self.node.name})")

    @property
    def network_stack(self):
        return self._executioner.network_stack

    @network_stack.setter
    def network_stack(self, network_stack):
        self._executioner.network_stack = network_stack

    def get_epr_reaction_handler(self):
        return self._executioner._handle_epr_response

    def _get_message_handlers(self):
        return {
            MessageType.SIGNAL: self._handle_signal,
            MessageType.SUBROUTINE: self._handle_subroutine,
            MessageType.INIT_NEW_APP: self._handle_init_new_app,
            MessageType.STOP_APP: self._handle_stop_app,
        }

    def add_network_stack(self, network_stack):
        self._executioner.network_stack = network_stack

    def run(self):
        while self.is_running:
            yield from self._handle_next_message()
            self._task_done()

    def _handle_next_message(self):
        self._logger.debug(f"Fetching item in the queue")
        item = yield from self._fetch_next_item()
        output = self._message_handlers[item.type](item.msg)
        if isinstance(output, GeneratorType):
            yield from output

    def _fetch_next_item(self):
        while True:
            try:
                item = self._message_queue.get(block=False)
            except Empty:
                # Wait a little until checking again
                yield self._sleeper.sleep()

            else:
                return item

    def _handle_subroutine(self, subroutine):
        subroutine = parse_binary_subroutine(subroutine)
        self._logger.debug(f"Executing next subroutine "
                           f"from app ID {subroutine.app_id}")
        yield from self._execute_subroutine(subroutine=subroutine)
        self._logger.debug(f"Marking subroutine as done")

    def _execute_subroutine(self, subroutine):
        yield from self._executioner.execute_subroutine(subroutine=subroutine)

    def _task_done(self):
        self._message_queue.task_done()

    def _handle_init_new_app(self, msg):
        app_id = msg.app_id
        max_qubits = msg.max_qubits
        circuit_rules = msg.circuit_rules
        self._logger.debug(f"Allocating a new "
                           f"unit module of size {max_qubits} for application with app ID {app_id}.\n"
                           f"Setting up circuit rules:\n{circuit_rules}")
        yield from self._executioner.init_new_application(
            app_id=app_id,
            max_qubits=max_qubits,
            circuit_rules=circuit_rules,
        )

    def _handle_stop_app(self, msg):
        app_id = msg.app_id
        self._logger.debug(f"Stopping application with app ID {app_id}")
        self._executioner.stop_application(app_id=app_id)

    def _handle_signal(self, signal):
        self._logger.debug(f"SubroutineHandler at node {self.node} handles the signal {signal}")
        if signal == Signal.STOP:
            self._logger.debug(f"SubroutineHandler at node {self.node} stops")
            self.stop()
        else:
            raise ValueError(f"Unkown signal {signal}")
