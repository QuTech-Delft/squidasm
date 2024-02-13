from __future__ import annotations

from netsquid_magic.models.perfect import PerfectLinkBuilder, PerfectLinkConfig
from netsquid_netbuilder.builder.network_builder import NetworkBuilder
from netsquid_netbuilder.modules.clinks.default import (
    DefaultCLinkBuilder,
    DefaultCLinkConfig,
)
from netsquid_netbuilder.modules.clinks.instant import (
    InstantCLinkBuilder,
    InstantCLinkConfig,
)
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceBuilder
from netsquid_netbuilder.modules.scheduler.fifo import FIFOScheduleBuilder
from netsquid_netbuilder.modules.scheduler.static import StaticScheduleBuilder
from netsquid_netbuilder.modules.qrep_chain_control.swap_asap.swap_asap_builder import SwapASAPConfig, SwapASAPBuilder


def get_test_network_builder() -> NetworkBuilder:
    builder = NetworkBuilder()
    # Default qdevice models registration
    builder.register_qdevice("generic", GenericQDeviceBuilder)

    # default link models registration
    # TODO create a inbuilt link for core or use
    builder.register_link("perfect", PerfectLinkBuilder, PerfectLinkConfig)

    # default clink models registration
    builder.register_clink("instant", InstantCLinkBuilder, InstantCLinkConfig)
    builder.register_clink("default", DefaultCLinkBuilder, DefaultCLinkConfig)

    # default schedulers
    builder.register_scheduler("static", StaticScheduleBuilder)
    builder.register_scheduler("fifo", FIFOScheduleBuilder)

    # default quantum repeater chain control
    builder.register_qrep_chain_control("swapASAP", SwapASAPBuilder, SwapASAPConfig)

    return builder
