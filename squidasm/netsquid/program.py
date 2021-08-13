import abc
from dataclasses import dataclass
from typing import Any, Dict, List

from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket


class ProgramContext:
    def __init__(
        self,
        netqasm_connection: BaseNetQASMConnection,
        csockets: Dict[str, Socket],
        epr_sockets: Dict[str, EPRSocket],
        app_id: int,
    ):
        self._connection = netqasm_connection
        self._csockets = csockets
        self._epr_sockets = epr_sockets
        self._app_id = app_id

    @property
    def connection(self) -> BaseNetQASMConnection:
        return self._connection

    @property
    def csockets(self) -> Dict[str, Socket]:
        return self._csockets

    @property
    def epr_sockets(self) -> Dict[str, EPRSocket]:
        return self._epr_sockets

    @property
    def app_id(self) -> int:
        return self._app_id


@dataclass
class ProgramMeta:
    name: str
    parameters: Dict[str, Any]
    csockets: List[str]
    epr_sockets: List[str]
    max_qubits: int


class Program(abc.ABC):
    @property
    def meta(self) -> ProgramMeta:
        raise NotImplementedError

    def run(self, context: ProgramContext) -> Dict[str, Any]:
        raise NotImplementedError
