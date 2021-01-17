import os

from netqasm.runtime.application import create_app_instance, create_network_cfg
from squidasm.run.simulate import simulate_application

# APP_DIR = "../netqasm/netqasm/examples/apps/teleport"
# APP_DIR = "../netqasm/netqasm/examples/apps/bb84"
APP_DIR = "../netqasm/netqasm/examples/apps/blind_grover"

if __name__ == "__main__":
    app_instance = create_app_instance(APP_DIR)
    # network_cfg = create_network_cfg(os.path.join(APP_DIR, "network.yaml"))

    # simulate_application(app_instance, 3, network_cfg)
    simulate_application(app_instance, 3)
