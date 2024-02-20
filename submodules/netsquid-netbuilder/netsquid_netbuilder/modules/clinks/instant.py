from __future__ import annotations

from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.models.delaymodels import FixedDelayModel
from netsquid.nodes.connections import DirectConnection
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig

from netsquid.nodes import Node


class InstantCLinkConfig(ICLinkConfig):
    pass


class InstantCLinkBuilder(ICLinkBuilder):
    @classmethod
    def build(
        cls, node1: Node, node2: Node, link_cfg: InstantCLinkConfig
    ) -> DirectConnection:

        channel1to2 = ClassicalChannel(
            name=f"Default channel {node1.name} to {node2.name}",
            delay=0,
            models={"delay_model": FixedDelayModel()},
        )
        channel2to1 = ClassicalChannel(
            name=f"Default channel {node2.name} to {node1.name}",
            delay=0,
            models={"delay_model": FixedDelayModel()},
        )

        conn = DirectConnection(
            name=f"Connection {node1.name} - {node2.name}",
            channel_AtoB=channel1to2,
            channel_BtoA=channel2to1,
        )
        return conn
