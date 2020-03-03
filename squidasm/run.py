import logging
from threading import Thread

from netqasm.sdk.shared_memory import reset_memories
from squidasm.backend import Backend


def run_applications(applications):
    """Executes functions containing application scripts,

    Parameters
    ----------
    applications : dict
        Keys should be names of nodes
        Values should be the functions
    """
    reset_memories()
    node_names = list(applications.keys())
    app_functions = list(applications.values())

    def run_backend():
        logging.debug(f"Starting netsquid backend thread with nodes {node_names}")
        backend = Backend(node_names)
        backend.start()
        logging.debug("End backend thread")

    # Start the application threads
    app_threads = []
    for app_function in app_functions:
        thread = Thread(target=app_function)
        thread.start()
        app_threads.append(thread)

    # Start the backend thread
    backend_thread = Thread(target=run_backend)
    backend_thread.start()

    # Join the application threads (not the backend)
    for app_thread in app_threads:
        app_thread.join()
