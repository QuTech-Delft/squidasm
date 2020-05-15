from multiprocessing.pool import ThreadPool
from yaml import dump
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

from netqasm.sdk.shared_memory import reset_memories
from netqasm.logging import get_netqasm_logger
from squidasm.backend import Backend
from squidasm.thread_util import as_completed
from squidasm.network_stack import reset_network

logger = get_netqasm_logger()


def reset():
    reset_memories()
    reset_network()


def run_applications(
    applications,
    post_function=None,
    instr_log_dir=None,
    network_config=None,
    output_file=None,
):
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
    reset()
    node_names = list(applications.keys())
    apps = [applications[node_name] for node_name in node_names]

    def run_backend():
        logger.debug(f"Starting netsquid backend thread with nodes {node_names}")
        backend = Backend(node_names, instr_log_dir=instr_log_dir, network_config=network_config)
        backend.start()
        if post_function is not None:
            output = post_function(backend)
        else:
            output = None
        logger.debug("End backend thread")
        return output

    with ThreadPool(len(node_names) + 1) as executor:
        # Start the backend thread
        backend_future = executor.apply_async(run_backend)

        # Start the application threads
        app_futures = []
        for app in apps:
            if isinstance(app, tuple):
                app_func, kwargs = app
                future = executor.apply_async(app_func, kwds=kwargs)
            else:
                future = executor.apply_async(app)
            app_futures.append(future)

        # Join the application threads and the backend
        names = ['backend'] + [f'app_{node_name}' for node_name in node_names]
        output = {}
        for future, name in as_completed([backend_future] + app_futures, names=names):
            output[name] = future.get()
            # if name == 'backend' and output is not None:
        if output_file is not None:
            save_output(output=output, output_file=output_file)

    reset()


def save_output(output, output_file):
    dump_yaml(data=output, file_path=output_file)


def dump_yaml(data, file_path):
    with open(file_path, 'w') as f:
        dump(data, f, Dumper=Dumper)
