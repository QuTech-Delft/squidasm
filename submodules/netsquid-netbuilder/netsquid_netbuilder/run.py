from __future__ import annotations

import typing
from typing import Dict

import netsquid as ns
from netsquid_magic.models.depolarise import DepolariseLinkBuilder, DepolariseLinkConfig
from netsquid_magic.models.heralded_double_click import (
    HeraldedDoubleClickLinkBuilder,
    HeraldedDoubleClickLinkConfig,
)
from netsquid_magic.models.heralded_single_click import (
    HeraldedSingleClickLinkBuilder,
    HeraldedSingleClickLinkConfig,
)
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
from netsquid_netbuilder.modules.links.nv import NVLinkBuilder, NVLinkConfig
from netsquid_netbuilder.modules.photonic_interface.depolarizing import (
    DepolarizingPhotonicInterfaceBuilder,
    DepolarizingPhotonicInterfaceConfig,
)
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceBuilder
from netsquid_netbuilder.modules.qdevices.nv import NVQDeviceBuilder
from netsquid_netbuilder.modules.scheduler.fifo import FIFOScheduleBuilder
from netsquid_netbuilder.modules.scheduler.static import StaticScheduleBuilder
from netsquid_netbuilder.protocol_base import BlueprintProtocol

if typing.TYPE_CHECKING:
    from netsquid_netbuilder.network import Network


def get_default_builder() -> NetworkBuilder:
    builder = NetworkBuilder()
    # Default qdevice models registration
    builder.register_qdevice("generic", GenericQDeviceBuilder)
    builder.register_qdevice("nv", NVQDeviceBuilder)

    # default link models registration
    builder.register_link("perfect", PerfectLinkBuilder, PerfectLinkConfig)
    builder.register_link("depolarise", DepolariseLinkBuilder, DepolariseLinkConfig)
    builder.register_link(
        "heralded-single-click",
        HeraldedSingleClickLinkBuilder,
        HeraldedSingleClickLinkConfig,
    )
    builder.register_link(
        "heralded-double-click",
        HeraldedDoubleClickLinkBuilder,
        HeraldedDoubleClickLinkConfig,
    )
    builder.register_link("nv", NVLinkBuilder, NVLinkConfig)

    builder.register_photonic_interface(
        "depolarise",
        DepolarizingPhotonicInterfaceBuilder,
        DepolarizingPhotonicInterfaceConfig,
    )

    # default clink models registration
    builder.register_clink("instant", InstantCLinkBuilder, InstantCLinkConfig)
    builder.register_clink("default", DefaultCLinkBuilder, DefaultCLinkConfig)

    # default schedulers
    builder.register_scheduler("static", StaticScheduleBuilder)
    builder.register_scheduler("fifo", FIFOScheduleBuilder)

    return builder


def run(network: Network, protocols: Dict[str, BlueprintProtocol]):
    # start all protocols
    network.start()
    for node_name, prot in protocols.items():
        context = network.get_protocol_context(node_name)
        prot.set_context(context)
        prot.start()

    sim_stats = ns.sim_run()

    # stop all protocols
    network.stop()
    for node_name, prot in protocols.items():
        prot.stop()

    return sim_stats
