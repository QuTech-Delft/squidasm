from __future__ import annotations

from netsquid_magic.models.perfect import PerfectLinkBuilder
from netsquid_netbuilder.clinks.default import DefaultCLinkBuilder
from netsquid_netbuilder.clinks.instant import InstantCLinkBuilder
from netsquid_netbuilder.network_builder import NetworkBuilder
from netsquid_netbuilder.qdevices.generic import GenericQDeviceBuilder
from netsquid_netbuilder.scheduler.fifo import FIFOScheduleBuilder
from netsquid_netbuilder.scheduler.static import StaticScheduleBuilder


def get_test_network_builder() -> NetworkBuilder:
    builder = NetworkBuilder()
    # Default qdevice models registration
    builder.register_qdevice("generic", GenericQDeviceBuilder)

    # default link models registration
    # TODO create a inbuilt link for core or use
    builder.register_link("perfect", PerfectLinkBuilder)

    # default clink models registration
    builder.register_clink("instant", InstantCLinkBuilder)
    builder.register_clink("default", DefaultCLinkBuilder)

    # default schedulers
    builder.register_scheduler("static", StaticScheduleBuilder)
    builder.register_scheduler("fifo", FIFOScheduleBuilder)

    return builder
