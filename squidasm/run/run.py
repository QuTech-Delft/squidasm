import logging
from importlib import reload
from multiprocessing.pool import ThreadPool
from typing import List

import netsquid as ns

from netqasm.sdk.shared_memory import reset_memories
from netqasm.logging.glob import get_netqasm_logger
from netqasm.util.yaml import dump_yaml
from netqasm.logging.output import save_all_struct_loggers, reset_struct_loggers
from netqasm.sdk.classical_communication import reset_socket_hub
from netqasm.runtime.app_config import AppConfig
from netqasm.runtime.settings import Formalism

from squidasm.backend.backend import Backend
from squidasm.thread_util import as_completed
from squidasm.network import reset_network
from squidasm.queues import reset_queues

logger = get_netqasm_logger()

_NS_FORMALISMS = {
    Formalism.STAB: ns.QFormalism.STAB,
    Formalism.KET: ns.QFormalism.KET,
    Formalism.DM: ns.QFormalism.DM,
}


def reset(save_loggers=False):
    if save_loggers:
        save_all_struct_loggers()
    ns.sim_reset()
    reset_memories()
    reset_network()
    reset_queues()
    reset_socket_hub()
    reset_struct_loggers()
    # Reset logging
    logging.shutdown()
    reload(logging)


def run_applications(
    app_cfgs: List[AppConfig],
    post_function=None,
    instr_log_dir=None,
    network_config=None,
    nv_config=None,
    results_file=None,
    formalism=Formalism.KET,
    flavour=None,
    use_app_config=True,  # whether to give app_config as argument to app's main()
):
    """Executes functions containing application scripts,

    Parameters
    ----------
    post_function : None or function
        A function to be applied to the backend (:class:`~.backend.Backend`)
        after the execution. This can be used for debugging, e.g. getting the
        quantum states after execution etc.
    """
    app_names = [app_cfg.app_name for app_cfg in app_cfgs]

    def run_backend():
        logger.debug(f"Starting netsquid backend thread with apps {app_names}")
        ns.set_qstate_formalism(_NS_FORMALISMS[formalism])
        backend = Backend(
            app_cfgs=app_cfgs,
            instr_log_dir=instr_log_dir,
            network_config=network_config,
            nv_config=nv_config,
            flavour=flavour
        )
        backend.start()
        if post_function is not None:
            result = post_function(backend)
        else:
            result = None
        logger.debug("End backend thread")
        return result

    with ThreadPool(len(app_cfgs) + 1) as executor:
        # Start the backend thread
        backend_future = executor.apply_async(run_backend)

        # Start the application threads
        app_futures = []
        for app_cfg in app_cfgs:
            inputs = app_cfg.inputs
            if use_app_config:
                inputs['app_config'] = app_cfg
            future = executor.apply_async(app_cfg.main_func, kwds=inputs)
            app_futures.append(future)

        # Join the application threads and the backend
        names = ['backend'] + [f'app_{app_name}' for app_name in app_names]
        results = {}
        for future, name in as_completed([backend_future] + app_futures, names=names):
            results[name] = future.get()
        if results_file is not None:
            save_results(results=results, results_file=results_file)

    reset(save_loggers=True)
    return results


def save_results(results, results_file):
    dump_yaml(data=results, file_path=results_file)
