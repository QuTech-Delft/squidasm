from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, Tuple

import netsquid as ns
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocol,
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor
from netsquid_nv.magic_distributor import NVSingleClickMagicDistributor

from squidasm.netsquid.config import QDeviceConfig, build_nv_qdevice
from squidasm.netsquid.context import NetSquidContext
from squidasm.netsquid.stack import NodeStack


class LinkType(Enum):
    PERFECT = auto()
    NV = auto()


def setup_stacks(
    qdevice_confg: QDeviceConfig, link_type: LinkType
) -> Tuple[NodeStack, NodeStack, MagicLinkLayerProtocol]:
    client_qdevice = build_nv_qdevice("nv_qdevice_client", cfg=qdevice_confg)
    client = NodeStack("client", qdevice=client_qdevice)
    server_qdevice = build_nv_qdevice("nv_qdevice_server", cfg=qdevice_confg)
    server = NodeStack("server", qdevice=server_qdevice)

    client.connect_to(server)
    NetSquidContext.set_nodes({client.node.ID: "client", server.node.ID: "server"})

    if link_type == LinkType.PERFECT:
        link_dist = PerfectStateMagicDistributor(nodes=[client.node, server.node])
    elif link_type == LinkType.NV:
        # TODO choose reasonable parameters
        link_dist = NVSingleClickMagicDistributor(
            nodes=[client.node, server.node],
            length_A=0.001,
            length_B=0.001,
            full_cycle=0.1,
            cycle_time=50,
            alpha=0.0,
        )
    else:
        raise ValueError

    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[client.node, server.node],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    client.assign_ll_protocol(link_prot)
    server.assign_ll_protocol(link_prot)

    return client, server, link_prot


def run_stacks(
    client: NodeStack, server: NodeStack, link: MagicLinkLayerProtocol
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    link.start()
    client.start()
    server.start()

    ns.sim_run()

    return client.host.get_results(), server.host.get_results()
