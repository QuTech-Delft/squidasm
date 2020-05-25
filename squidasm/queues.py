from queue import Queue

from netqasm.messages import Signal

_QUEUES = {}


def get_queue(node_name, key=None, create_new=False):
    absolute_key = (node_name, key)
    queue = _QUEUES.get(absolute_key)
    if queue is None:
        if create_new:
            queue = Queue()
            _QUEUES[absolute_key] = queue
        else:
            raise RuntimeError(f"Trying to get queue with name {node_name}, but it doesn't exist.")
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
