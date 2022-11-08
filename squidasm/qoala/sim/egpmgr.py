from typing import Dict, Generator

from squidasm.qoala.sim.egp import EgpProtocol


class EgpManager:
    def __init__(self) -> None:
        self._egps: Dict[int, EgpProtocol] = {}

    def add_egp(self, remote_id: int, prot: EgpProtocol) -> None:
        self._egps[remote_id] = prot

    def get_egp(self, remote_id: int) -> EgpProtocol:
        return self._egps[remote_id]
