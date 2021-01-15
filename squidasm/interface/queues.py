from queue import Queue
from time import sleep
from timeit import default_timer as timer
from typing import Dict

from netqasm.backend.messages import Signal


class TaskQueue:
    """Subclass Queue which allow to wait for a specific task to be done and not only all"""

    def __init__(self):
        self._queue = Queue()
        self._fin_tasks = set()

    def reset(self):
        self._queue = Queue()
        self._fin_tasks = set()

    def qsize(self):
        return self._queue.qsize()

    def empty(self):
        return self._queue.empty()

    def full(self):
        return self._queue.full()

    def get(self, block=True, timeout=None):
        return self._queue.get(block=block, timeout=timeout)

    def put(self, item, block=True, timeout=None):
        return self._queue.put(item=item, block=block, timeout=timeout)

    def task_done(self, item):
        self._fin_tasks.add(item)
        return self._queue.task_done()

    def join_task(self, item):
        while item not in self._fin_tasks:
            pass
        # When the task has finished, remove it to prevent future
        # messages that are exactly the same to immediately be finished.
        self._fin_tasks.remove(item)

    def join(self):
        return self._queue.join()


# def wait_for_queue_creation(absolute_key, timeout=5.0):
#     t_start = timer()

#     while True:
#         queue = _QUEUES.get(absolute_key)
#         if queue is not None:
#             return queue

#         sleep(0.1)
#         now = timer()
#         if (now - t_start) > timeout:
#             raise TimeoutError(f"No queue found with key {absolute_key}. (Waited for {timeout} seconds)")


# def signal_queue(node_name, signal, key=None):
#     """Puts a signal on a queue"""
#     if not isinstance(signal, Signal):
#         raise TypeError(f"signal should be of type Signal, not {type(signal)}")
#     queue = get_queue(node_name=node_name, key=key)
#     queue.put(signal)


# def stop_queue(node_name, key=None):
#     """Signals a queue to stop"""
#     signal_queue(node_name=node_name, signal=Signal.STOP, key=key)


class QueueManager:
    _QUEUES: Dict[str, TaskQueue] = {}

    @classmethod
    def create_queue(cls, node_name: str) -> TaskQueue:
        if cls._QUEUES.get(node_name) is not None:
            raise RuntimeError(f"Queue for node {node_name} already exists.")
        queue = TaskQueue()
        cls._QUEUES[node_name] = queue
        return queue

    @classmethod
    def get_queue(cls, node_name: str) -> TaskQueue:
        queue = cls._QUEUES.get(node_name)
        if queue is None:
            raise RuntimeError(f"Queue for node {node_name} does not exist.")
        return queue

    @classmethod
    def reset_queues(cls) -> None:
        for queue in cls._QUEUES.values():
            queue.reset()

    @classmethod
    def destroy_queues(cls) -> None:
        while len(cls._QUEUES) > 0:
            cls._QUEUES.popitem()
