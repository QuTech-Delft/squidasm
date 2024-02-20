import logging

import netsquid as ns
from netsquid_netbuilder.base_configs import NetworkConfig
from netsquid_driver.logger import SnippetLogManager
from netsquid_netbuilder.run import get_default_builder, run
from protocols import TeleportationReceiverProtocol, TeleportationSenderProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
SnippetLogManager.set_log_level(logging.ERROR)

builder = get_default_builder()

cfg = NetworkConfig.from_file("config_repeater.yaml")
network = builder.build(cfg)


sim_stats = run(
    network,
    {
        "h1n0": TeleportationSenderProtocol("h2n0"),
        "h2n0": TeleportationReceiverProtocol("h1n0"),
    },
)
print(sim_stats)
