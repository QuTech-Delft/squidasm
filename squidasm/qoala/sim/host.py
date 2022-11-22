from __future__ import annotations

from typing import Dict, Generator

import netsquid as ns
from netsquid.protocols import Protocol

from pydynaa import EventExpression, EventType
from squidasm.qoala.runtime.environment import LocalEnvironment
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.hostprocessor import HostProcessor, IqoalaProcess


class Host(Protocol):
    """NetSquid protocol representing a Host."""

    def __init__(
        self,
        comp: HostComponent,
        local_env: LocalEnvironment,
        asynchronous: bool = False,
    ) -> None:
        """Host protocol constructor.

        :param comp: NetSquid component representing the Host
        """
        super().__init__(name=f"{comp.name}_protocol")

        # References to objects.
        self._comp = comp
        self._local_env = local_env

        # Owned objects.
        self._interface = HostInterface(comp, local_env)
        self._processor = HostProcessor(self._interface, asynchronous)

    @property
    def interface(self) -> HostInterface:
        return self._interface

    @interface.setter
    def interface(self, interface: HostInterface) -> None:
        self._interface = interface
        self._processor._interface = interface

    @property
    def processor(self) -> HostProcessor:
        return self._processor

    @property
    def local_env(self) -> LocalEnvironment:
        return self._local_env

    def start(self) -> None:
        assert self._interface is not None
        super().start()
        self._interface.start()

    def stop(self) -> None:
        self._interface.stop()
        super().stop()

    def create_csocket(self, remote_name: str) -> ClassicalSocket:
        return ClassicalSocket(self._interface, remote_name)
