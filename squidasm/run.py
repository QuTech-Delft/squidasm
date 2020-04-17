import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from netqasm.sdk.shared_memory import reset_memories
from squidasm.backend import Backend


def run_applications(applications, post_function=None):
    """Executes functions containing application scripts,

    Parameters
    ----------
    applications : dict
        Keys should be names of nodes
        Values should be the functions
    post_function : None or function
        A function to be applied to the backend (:class:`~.backend.Backend`)
        after the execution. This can be used for debugging, e.g. getting the
        quantum states after execution etc.
    """
    reset_memories()
    node_names = list(applications.keys())
    app_functions = list(applications.values())

    def run_backend():
        logging.debug(f"Starting netsquid backend thread with nodes {node_names}")
        backend = Backend(node_names)
        backend.start()
        if post_function is not None:
            post_function(backend)
        logging.debug("End backend thread")

    with ThreadPoolExecutor(max_workers=len(node_names) + 1) as executor:
        # Start the application threads
        app_futures = []
        for app_function in app_functions:
            future = executor.submit(app_function)
            app_futures.append(future)

        # Start the backend thread
        backend_future = executor.submit(run_backend)

        # Join the application threads and the backend
        for future in as_completed([backend_future] + app_futures):
            future.result()

    reset_memories()
