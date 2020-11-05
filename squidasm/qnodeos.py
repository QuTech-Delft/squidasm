import random
from queue import Empty
from types import GeneratorType

from pydynaa import EventType, EventExpression
from netsquid.protocols import NodeProtocol
from netsquid_magic.sleeper import Sleeper

from netqasm.backend.messages import MessageType, Signal
from netqasm.backend.messages import deserialize_host_msg as deserialize_message
from netqasm.lang.instr.flavour import VanillaFlavour, NVFlavour, Flavour
from netqasm.backend.qnodeos import BaseSubroutineHandler

from squidasm.executioner.vanilla import VanillaNetSquidExecutioner
from squidasm.executioner.nv import NVNetSquidExecutioner
from squidasm.queues import get_queue


# TODO how to know which are wait events?
_WAIT_EVENT_NAMES = ["ANY_EVENT", "LOOP", "WAIT"]


def is_waiting_event(event):
    if isinstance(event, EventType):
        tp = event
    elif isinstance(event, EventExpression):
        tp = event.atomic_type
        if tp is None:
            raise ValueError("Not an atomic event expression")
    else:
        raise TypeError(f"Not an Event or EventExpression, but {type(event)}")
    return tp.name in _WAIT_EVENT_NAMES


class Task:
    """Keeps track of a task qnodeos has and if it's finished or waiting.
    """

    def __init__(self, gen, msg):
        self._gen = gen
        self._msg = msg
        self._next_event = None
        self._is_finished = False
        self._is_waiting = False

    @property
    def msg(self):
        return self._msg

    @property
    def is_finished(self):
        return self._is_finished

    @property
    def is_waiting(self):
        return self._is_waiting

    def pop_next_event(self):
        if self._next_event is None:
            self.update_next_event()
        if self.is_finished:
            raise IndexError("No more events")
        next_event = self._next_event
        self._next_event = None
        return next_event

    def update_next_event(self):
        if self._next_event is not None:
            return
        try:
            next_event = next(self._gen)
        except StopIteration:
            self._is_finished = True
            self._is_waiting = False
            return

        self._is_waiting = is_waiting_event(next_event)
        self._next_event = next_event


class SubroutineHandler(BaseSubroutineHandler, NodeProtocol):
    def __init__(self, node, instr_log_dir=None, flavour: Flavour = None,
                 instr_proc_time: int = 0, host_latency: int = 0):
        """An extremely simplified version of QNodeOS for handling NetQASM subroutines"""
        BaseSubroutineHandler.__init__(
            self,
            name=node.name,
            instr_log_dir=instr_log_dir,
            flavour=flavour,
            node=node,
            instr_proc_time=instr_proc_time,
            host_latency=host_latency
        )
        NodeProtocol.__init__(self, node=node)

        self._message_queue = get_queue(self.node.name, create_new=True)

        # Keep track of tasks to execute
        self._subroutine_tasks = []
        self._other_tasks = []

        self._sleeper = Sleeper()

    @classmethod
    def _get_executioner_class(cls, flavour=None):
        if flavour is None or isinstance(flavour, VanillaFlavour):
            return VanillaNetSquidExecutioner
        elif isinstance(flavour, NVFlavour):
            return NVNetSquidExecutioner
        else:
            raise ValueError(f"Flavour {flavour} is not supported.")

    @property
    def has_active_apps(self):
        return len(self._active_app_ids) > 0

    @property
    def network_stack(self):
        return self._executioner.network_stack

    @network_stack.setter
    def network_stack(self, network_stack):
        self._executioner.network_stack = network_stack

    def get_epr_reaction_handler(self):
        return self._executioner._handle_epr_response

    def run(self):
        while self.is_running:
            # Check if there is a new message
            # self._logger.debug('Checking for next message')
            raw_msg = self._next_message()
            if raw_msg is not None:
                msg = deserialize_message(raw_msg)
                self._handle_message(msg=msg)
            ev = self._get_next_task_event()
            if ev is None:
                # No tasks so wait a bit before checking next msg
                self._logger.debug('No more events so wait for next message')
                yield self._sleeper.sleep()
            else:
                yield ev

    def _handle_message(self, msg):
        self._logger.info(f'Handle message {msg}')
        output = self._message_handlers[msg.TYPE](msg)
        if isinstance(output, GeneratorType):
            # If generator then add to this to the current task
            # Distinguish subroutines from others to prioritize others
            if msg.TYPE == MessageType.SUBROUTINE:
                self._logger.debug('Adding to subroutine tasks')
                self._subroutine_tasks.append(Task(gen=output, msg=msg))
            else:
                self._logger.debug('Adding to other tasks')
                self._other_tasks.append(Task(gen=output, msg=msg))
        else:
            # No generator so directly finished
            self._mark_message_finished(msg=msg)

    def _get_next_task_event(self):
        # Execute other tasks (non subroutine first and in order)
        task = self._get_next_other_task()
        if task is not None:
            self._logger.debug('Executing other task')
            try:
                return task.pop_next_event()
            except IndexError:
                return None
        # Only subroutine handlers left
        # Execute in order unless a subroutine is waiting
        # self._logger.debug('Executing subroutine task')
        task = self._get_next_subroutine_task()
        if task is None:
            self._logger.debug('No more subroutine tasks')
            return None
        else:
            try:
                return task.pop_next_event()
            except IndexError:
                return None

    def _mark_message_finished(self, msg):
        # `msg` is here just for prettier log
        self._logger.debug(f"Marking message {msg} as done")
        self._finished_messages.append(bytes(msg))
        self._task_done(item=bytes(msg))

    def _get_next_other_task(self):
        if len(self._other_tasks) == 0:
            return None
        task = self._other_tasks[0]
        if task.is_finished:
            self._other_tasks.pop(0)
            self._mark_message_finished(msg=task.msg)
            return self._get_next_other_task()
        return task

    def _get_next_subroutine_task(self):
        # Check for finished tasks
        to_remove = []
        for i, task in enumerate(self._subroutine_tasks):
            if task.is_finished:
                to_remove.append(i)
                self._mark_message_finished(msg=task.msg)
        for i in reversed(to_remove):
            self._subroutine_tasks.pop(i)
        if len(self._subroutine_tasks) == 0:
            return None
        for i, task in enumerate(self._subroutine_tasks):
            if not task.is_waiting:
                return task
        # All tasks are waiting so return first
        # self._logger.info('All subroutines are waiting')
        return random.choice(self._subroutine_tasks)

    def _next_message(self):
        try:
            item = self._message_queue.get(block=False)
        except Empty:
            item = None
        return item

    def _task_done(self, item):
        self._message_queue.task_done(item=item)

    def _handle_signal(self, signal):
        self._logger.debug(f"SubroutineHandler at node {self.node} handles the signal {signal}")
        if Signal(signal.signal) == Signal.STOP:
            self._logger.debug(f"SubroutineHandler at node {self.node} stops")
            self.stop()
        else:
            raise ValueError(f"Unkown signal {signal}")

    def stop(self):
        NodeProtocol.stop(self)
