import logging

import netsquid as ns

from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.run import get_default_builder, run

from protocols import TeleportationSenderProtocol, TeleportationReceiverProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
LogManager.set_log_level(logging.ERROR)

builder = get_default_builder()

cfg = StackNetworkConfig.from_file("config_repeater.yaml")
network = builder.build(cfg, hacky_is_squidasm_flag=False)


sim_stats = run(
    network,
    {
        "hub1_node_0": TeleportationSenderProtocol("hub2_node_0"),
        "hub2_node_0": TeleportationReceiverProtocol("hub1_node_0"),
    },
)
print(sim_stats)
