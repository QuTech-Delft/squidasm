import logging

import netsquid as ns
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.run import get_default_builder, run
from protocols import TeleportationReceiverProtocol, TeleportationSenderProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
LogManager.set_log_level(logging.ERROR)

builder = get_default_builder()

cfg = StackNetworkConfig.from_file("config_repeater.yaml")
network = builder.build(cfg, hacky_is_squidasm_flag=False)


sim_stats = run(
    network,
    {
        "h1n0": TeleportationSenderProtocol("h2n0"),
        "h2n0": TeleportationReceiverProtocol("h1n0"),
    },
)
print(sim_stats)
