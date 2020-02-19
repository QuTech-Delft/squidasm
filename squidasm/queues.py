from queue import Queue
from enum import Enum, auto

_QUEUES = {}


class Signal(Enum):
    STOP = auto()


def get_queue(node_name, key=None):
    absolute_key = (node_name, key)
    queue = _QUEUES.get(absolute_key)
    if queue is None:
        queue = Queue()
        _QUEUES[absolute_key] = queue
    return queue


def signal_queue(node_name, signal, key=None):
    """Puts a signal on a queue"""
    if not isinstance(signal, Signal):
        raise TypeError(f"signal should be of type Signal, not {type(signal)}")
    queue = get_queue(node_name=node_name, key=key)
    queue.put(signal)


def stop_queue(node_name, key=None):
    """Signals a queue to stop"""
    signal_queue(node_name=node_name, signal=Signal.STOP, key=key)
