from __future__ import annotations
from typing import Optional
from netsquid.nodes.connections import DirectConnection
from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.models.delaymodels import FixedDelayModel
from blueprint.clinks.interface import ICLinkConfig, ICLinkBuilder
from squidasm.sim.stack.stack import ProcessingNode


class DefaultCLinkConfig(ICLinkConfig):
    delay: Optional[float] = None
    distance: Optional[float] = None
    speed_of_light: float = 200000


class DefaultCLinkBuilder(ICLinkBuilder):
    @classmethod
    def build(cls, node1: ProcessingNode, node2: ProcessingNode, link_cfg: DefaultCLinkConfig) -> DirectConnection:
        if isinstance(link_cfg, dict):
            link_cfg = DefaultCLinkConfig(**link_cfg)
        if link_cfg.delay is None and link_cfg.distance is None:
            raise Exception("Model requires delay or distance")
        if link_cfg.delay is not None and link_cfg.distance is not None:
            raise Exception("Model can only use one parameter")
        if link_cfg.distance is not None:
            link_cfg.delay = link_cfg.distance / link_cfg.speed_of_light * 1E9

        channel1to2 = ClassicalChannel(name=f"Default channel {node1.name} to {node2.name}",
                                       models={"delay_model": FixedDelayModel(delay=link_cfg.delay)})
        channel2to1 = ClassicalChannel(name=f"Default channel {node2.name} to {node1.name}",
                                       models={"delay_model": FixedDelayModel(delay=link_cfg.delay)})

        conn = DirectConnection(name=f"Connection {node1.name} - {node2.name}", channel_AtoB=channel1to2,
                                channel_BtoA=channel2to1)
        return conn

