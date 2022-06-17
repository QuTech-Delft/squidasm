import abc
from dataclasses import dataclass
from typing import Any, Dict, List

from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection

from squidasm.qoala.lang.lhr import LhrProgram


class ProgramContext:
    def __init__(
        self,
        netqasm_connection: BaseNetQASMConnection,
        csockets: Dict[str, Socket],
        app_id: int,
    ):
        self._connection = netqasm_connection
        self._csockets = csockets
        self._app_id = app_id

    @property
    def connection(self) -> BaseNetQASMConnection:
        return self._connection

    @property
    def csockets(self) -> Dict[str, Socket]:
        return self._csockets

    @property
    def app_id(self) -> int:
        return self._app_id




@dataclass
class ProgramInstance:
    program: LhrProgram
    inputs: Dict[str, Any]
    num_iterations: int
    deadline: float
