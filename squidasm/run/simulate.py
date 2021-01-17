import os
import sys
import importlib
from typing import List, Any, Optional

from netqasm.runtime.settings import Formalism, Flavour
from netqasm.runtime.interface.config import (
    default_network_config, parse_network_config, NetworkConfig)
from netqasm.util.yaml import load_yaml
from netqasm.sdk.config import LogConfig
# from netqasm.runtime.env import load_app_files, load_app_config_file, load_roles_config
from netqasm.runtime import env
from squidasm.sim.network.nv_config import parse_nv_config, NVConfig

from squidasm.run.runtime_mgr import (
    SquidAsmRuntimeManager, Application, ApplicationInstance, Program)


def load_yaml_file(path: str) -> Any:
    if not os.path.exists(path):
        raise ValueError(f"Could not read file {path} since it does not exist.")
    return load_yaml(path)


def create_network_cfg(network_config_file: str = None) -> NetworkConfig:
    if network_config_file is None:
        network_cfg = default_network_config(["delft", "amsterdam"])
    else:
        yaml_dict = load_yaml_file(network_config_file)
        network_cfg = parse_network_config(yaml_dict)
    return network_cfg


def create_nv_cfg(nv_config_file: str = None) -> NVConfig:
    if nv_config_file is None:
        nv_cfg = None
    else:
        yaml_dict = load_yaml_file(nv_config_file)
        nv_cfg = parse_nv_config(yaml_dict)
    return nv_cfg


def create_app_instance(app_dir: str = None) -> ApplicationInstance:
    """
    Create an Application Instance based on files in a directory.
    Uses the current working directory if `app_dir` is None.
    """
    app_dir = os.path.abspath(".") if app_dir is None else os.path.expanduser(app_dir)
    sys.path.append(app_dir)
    program_files = env.load_app_files(app_dir)

    programs = []
    program_inputs = {}
    for party, prog_file in program_files.items():
        prog_module = importlib.import_module(prog_file[:-len('.py')])
        main_func = getattr(prog_module, "main")
        prog = Program(party=party, entry=main_func, args=["app_config"], results=[])
        programs += [prog]
        prog_inputs = env.load_app_config_file(app_dir, party)
        program_inputs[party] = prog_inputs

    roles_cfg_path = os.path.abspath(".") if app_dir is None else os.path.join(app_dir, "roles.yaml")
    party_alloc = env.load_roles_config(roles_cfg_path)
    party_alloc = {prog.party: prog.party for prog in programs} if party_alloc is None else party_alloc

    app = Application(programs=programs, metadata=None)
    app_instance = ApplicationInstance(
        app=app,
        program_inputs=program_inputs,
        network=None,
        party_alloc=party_alloc,
        logging_cfg=None,
    )

    return app_instance


def simulate_application(
    app_instance: ApplicationInstance,
    num_rounds: int = 1,
    network_cfg: Optional[NetworkConfig] = None,
    nv_cfg: Optional[NVConfig] = None,
    log_cfg: Optional[LogConfig] = None,
):
    mgr = SquidAsmRuntimeManager()

    if network_cfg is None:
        node_names = [name for name in app_instance.party_alloc.keys()]
        network_cfg = default_network_config(node_names=node_names)

    mgr.set_network(cfg=network_cfg, nv_cfg=nv_cfg)

    log_cfg = LogConfig() if log_cfg is None else log_cfg
    app_instance.logging_cfg = log_cfg

    log_dir = os.path.abspath("./log") if log_cfg.log_dir is None else log_cfg.log_dir
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)

    mgr.start_backend()

    for i in range(num_rounds):
        print(f"\niteration {i}")

        if log_cfg.split_runs or timed_log_dir is None:
            # create new timed directory for next run or for first run
            timed_log_dir = env.get_timed_log_dir(log_dir)

        mgr.backend_log_dir = timed_log_dir
        app_instance.logging_cfg.log_subroutines_dir = timed_log_dir
        app_instance.logging_cfg.comm_log_dir = timed_log_dir
        results = mgr.run_app(app_instance)
        print(f"results: {results}")

    mgr.stop_backend()
