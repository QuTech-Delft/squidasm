from typing import Optional

from netsquid.protocols import Protocol, Signals

from netsquid_netbuilder.network import ProtocolContext


class BlueprintProtocol(Protocol):
    PEER = "Bob"

    def __init__(self):
        self.context: Optional[ProtocolContext] = None
        self.add_signal(Signals.FINISHED)

    def set_context(self,  context: ProtocolContext):
        self.context = context

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()