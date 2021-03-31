import logging

from netqasm.logging.glob import set_log_level
from netqasm.runtime.application import app_instance_from_path, network_cfg_from_path

from squidasm.run.multithread.simulate import simulate_application

APP_DIR = "../netqasm/netqasm/examples/apps/teleport"


def main():
    set_log_level(logging.INFO)
    app_instance = app_instance_from_path(APP_DIR)
    network_cfg = network_cfg_from_path(APP_DIR)

    simulate_application(app_instance, 3, network_cfg)


if __name__ == "__main__":
    main()
