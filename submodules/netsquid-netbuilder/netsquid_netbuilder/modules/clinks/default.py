from __future__ import annotations

from typing import Optional

from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.models.delaymodels import FixedDelayModel
from netsquid.nodes.connections import DirectConnection
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig

from squidasm.sim.stack.stack import ProcessingNode


class DefaultCLinkConfig(ICLinkConfig):
    delay: Optional[float] = None
    length: Optional[float] = None
    speed_of_light: float = 200000


class DefaultCLinkBuilder(ICLinkBuilder):
    @classmethod
    def build(
        cls, node1: ProcessingNode, node2: ProcessingNode, link_cfg: DefaultCLinkConfig
    ) -> DirectConnection:
        link_cfg = cls._pre_process_config(link_cfg)

        channel1to2 = ClassicalChannel(
            name=f"Default channel {node1.name} to {node2.name}",
            models={"delay_model": FixedDelayModel(delay=link_cfg.delay)},
        )
        channel2to1 = ClassicalChannel(
            name=f"Default channel {node2.name} to {node1.name}",
            models={"delay_model": FixedDelayModel(delay=link_cfg.delay)},
        )

        conn = DirectConnection(
            name=f"Connection {node1.name} - {node2.name}",
            channel_AtoB=channel1to2,
            channel_BtoA=channel2to1,
        )
        return conn

    @classmethod
    def _pre_process_config(cls, link_cfg: DefaultCLinkConfig) -> DefaultCLinkConfig:
        if isinstance(link_cfg, dict):
            link_cfg = DefaultCLinkConfig(**link_cfg)
        if link_cfg.delay is None and (
            link_cfg.length is None or link_cfg.speed_of_light is None
        ):
            raise ValueError(
                f"{cls.__name__} model config requires a delay"
                f" or distance with speed of light specification"
            )
        if link_cfg.delay is not None and link_cfg.length is not None:
            raise ValueError(
                f"{cls.__name__} model config can only use delay or distance, but both where specified"
            )
        if link_cfg.length is not None:
            link_cfg.delay = link_cfg.length / link_cfg.speed_of_light * 1e9
        return link_cfg
