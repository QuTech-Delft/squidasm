from queue import Queue
from time import sleep
from timeit import default_timer as timer

from netqasm.messages import Signal

_QUEUES = {}


def get_queue(node_name, key=None, create_new=False, wait_for=5.0):
    """ wait_for: time in secs to wait for queue to be created if not exists """
    absolute_key = (node_name, key)
    queue = _QUEUES.get(absolute_key)
    if queue is None:
        if create_new:
            queue = Queue()
            _QUEUES[absolute_key] = queue
        else:
            queue = wait_for_queue_creation(absolute_key, wait_for)
    return queue


def wait_for_queue_creation(absolute_key, timeout=5.0):
    t_start = timer()

    while True:
        queue = _QUEUES.get(absolute_key)
        if queue is not None:
            return queue

        sleep(0.1)
        now = timer()
        if (now - t_start) > timeout:
            raise TimeoutError(f"No queue found with key {absolute_key}. (Waited for {timeout} seconds)")


def signal_queue(node_name, signal, key=None):
    """Puts a signal on a queue"""
    if not isinstance(signal, Signal):
        raise TypeError(f"signal should be of type Signal, not {type(signal)}")
    queue = get_queue(node_name=node_name, key=key)
    queue.put(signal)


def stop_queue(node_name, key=None):
    """Signals a queue to stop"""
    signal_queue(node_name=node_name, signal=Signal.STOP, key=key)
