import os
import shutil
import pickle
from runpy import run_path
from datetime import datetime

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from netqasm.logging import (
    set_log_level,
    _LOG_FIELD_DELIM,
    _LOG_HDR_DELIM,
    _InstrLogHeaders,
    get_netqasm_logger,
)
from .run import run_applications

logger = get_netqasm_logger()


def load_yaml(file_path):
    with open(file_path, 'r') as f:
        data = load(f, Loader=Loader)
    return data


def load_app_config(app_dir, node_name):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f"{node_name}{ext}")
    if os.path.exists(file_path):
        config = load_yaml(file_path=file_path)
    else:
        config = None
    if config is None:
        return {}
    else:
        return config


def get_network_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'network{ext}')
    return file_path


def load_network_config(network_config_file):
    if os.path.exists(network_config_file):
        return load_yaml(file_path=network_config_file)
    else:
        return None


def load_app_files(app_dir):
    app_tag = 'app_'
    ext = '.py'
    app_files = {}
    for entry in os.listdir(app_dir):
        if entry.startswith(app_tag) and entry.endswith('.py'):
            node_name = entry[len(app_tag):-len(ext)]
            app_files[node_name] = entry
    if len(app_files) == 0:
        raise ValueError(f"directory {app_dir} does not seem to be a application directory (no app_xxx.py files)")
    return app_files


def get_log_dir(app_dir):
    log_dir = os.path.join(app_dir, "log")
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    return log_dir


def get_timed_log_dir(log_dir):
    now = datetime.now().strftime('%Y%m%d-%H%M%S')
    timed_log_dir = os.path.join(log_dir, now)
    if not os.path.exists(timed_log_dir):
        os.mkdir(timed_log_dir)
    return timed_log_dir


_LAST_LOG = 'LAST'


def process_log(log_dir):
    # Add host line numbers to logs
    _add_hln_to_logs(log_dir)

    # Make this the last log
    base_log_dir, log_dir_name = os.path.split(log_dir)
    last_log_dir = os.path.join(base_log_dir, _LAST_LOG)
    if os.path.exists(last_log_dir):
        shutil.rmtree(last_log_dir)
    shutil.copytree(log_dir, last_log_dir)


def _add_hln_to_logs(log_dir):
    log_ext = '.log'
    for entry in os.listdir(log_dir):
        if entry.endswith(log_ext):
            node_name = entry[:-len(log_ext)]
            log_file_path = os.path.join(log_dir, entry)
            subroutines_file_path = os.path.join(log_dir, f"subroutines_{node_name}.pkl")
            _add_hln_to_log(log_file_path=log_file_path, subroutines_file_path=subroutines_file_path)


def _add_hln_to_log(log_file_path, subroutines_file_path):
    if not os.path.exists(subroutines_file_path):
        return

    # Read subroutines and log file
    with open(subroutines_file_path, 'rb') as f:
        subroutines = pickle.load(f)
    with open(log_file_path, 'r') as f:
        log_lines = f.readlines()

    # Update log lines
    for i, log_line in enumerate(log_lines):
        log_lines[i] = _add_hln_to_log_line(subroutines, log_line)

    # Write updated log file
    with open(log_file_path, 'w') as f:
        f.writelines(log_lines)


def _add_hln_to_log_line(subroutines, log_line):
    fields = log_line.split(_LOG_FIELD_DELIM)
    prc = None
    sid = None
    for field in fields:
        if _LOG_HDR_DELIM in field:
            hdr, value = field.split(_LOG_HDR_DELIM)
            if hdr == _InstrLogHeaders.PRC.value:
                prc = int(value)
            if hdr == _InstrLogHeaders.SID.value:
                sid = int(value)
    if prc is None:
        raise RuntimeError("Couldn't find PRC field in log file")
    if sid is None:
        raise RuntimeError("Couldn't find SID field in log file")
    subroutine = subroutines[sid]
    hln = subroutine.commands[prc].lineno
    fields.insert(-2, f"{_InstrLogHeaders.HLN.value}{_LOG_HDR_DELIM}{hln}")
    log_line = _LOG_FIELD_DELIM.join(fields)
    return log_line


def get_post_function_path(app_dir):
    return os.path.join(app_dir, 'post_function.py')


def load_post_function(post_function_file):
    if not os.path.exists(post_function_file):
        return None
    return run_path(post_function_file)['main']


def get_output_path(timed_log_dir):
    return os.path.join(timed_log_dir, 'output.yaml')


def simulate_apps(
    app_dir=None,
    track_lines=True,
    app_config_dir=None,
    network_config_file=None,
    log_dir=None,
    log_level="WARNING",
    post_function_file=None,
    output_file=None,
):

    set_log_level(log_level)

    # Setup paths to directories
    if app_dir is None:
        app_dir = os.path.abspath('.')
    else:
        app_dir = os.path.expanduser(app_dir)
    app_files = load_app_files(app_dir)
    if app_config_dir is None:
        app_config_dir = app_dir
    else:
        app_config_dir = os.path.expanduser(app_config_dir)
    if network_config_file is None:
        network_config_file = get_network_config_path(app_dir)
    else:
        network_config_file = os.path.expanduser(network_config_file)
    if log_dir is None:
        log_dir = get_log_dir(app_dir=app_dir)
    else:
        log_dir = os.path.expanduser(log_dir)
    timed_log_dir = get_timed_log_dir(log_dir=log_dir)
    if post_function_file is None:
        post_function_file = get_post_function_path(app_dir)
    if output_file is None:
        output_file = get_output_path(timed_log_dir)

    # Load app functions and configs to run
    applications = {}
    for node_name, app_file in app_files.items():
        app_main = run_path(os.path.join(app_dir, app_file))['main']
        app_config = load_app_config(app_config_dir, node_name)
        app_config['track_lines'] = track_lines
        app_config['log_subroutines_dir'] = timed_log_dir
        applications[node_name] = app_main, app_config

    network_config = load_network_config(network_config_file)

    # Load post function if exists
    post_function = load_post_function(post_function_file)

    run_applications(
        applications=applications,
        network_config=network_config,
        instr_log_dir=timed_log_dir,
        post_function=post_function,
        output_file=output_file,
    )

    process_log(log_dir=timed_log_dir)
