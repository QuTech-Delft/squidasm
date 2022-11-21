from typing import Dict

from squidasm.qoala.sim.egp import EgpProtocol


class NoEgpError(Exception):
    pass


class EgpManager:
    def __init__(self) -> None:
        self._egps: Dict[int, EgpProtocol] = {}

    def add_egp(self, remote_id: int, prot: EgpProtocol) -> None:
        self._egps[remote_id] = prot

    def get_egp(self, remote_id: int) -> EgpProtocol:
        if remote_id not in self._egps:
            raise NoEgpError
        return self._egps[remote_id]

    @property
    def egps(self) -> Dict[int, EgpProtocol]:
        return self._egps
