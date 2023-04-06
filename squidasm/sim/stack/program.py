import abc
from dataclasses import dataclass
from typing import Any, Dict, List

from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.epr_socket import EPRSocket


class ProgramContext:
    """Container object for providing the correct NetQASM connection and sockets to a program."""

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
        """Returns the NetQASM connection for the host."""
        return self._connection

    @property
    def csockets(self) -> Dict[str, Socket]:
        """Returns a dictionary of available classical sockets for the program.
        The dictionary keys are the stack names."""
        return self._csockets

    @property
    def epr_sockets(self) -> Dict[str, EPRSocket]:
        """Returns a dictionary of available epr sockets for the program. The dictionary keys are the stack names."""
        return self._epr_sockets

    @property
    def app_id(self) -> int:
        """Returns the ID of the app."""
        return self._app_id


@dataclass
class ProgramMeta:
    """Contains various meta information regarding the program."""

    name: str
    """Name of the program."""
    csockets: List[str]
    """List of nodes names with whom the program uses a classical connection."""
    epr_sockets: List[str]
    """List of nodes names with whom the program uses a quantum connection."""
    max_qubits: int
    """The number of qubits that the program requires."""


class Program(abc.ABC):
    """
    Base class defining an interface for application programs to adhere to.
    """

    @property
    def meta(self) -> ProgramMeta:
        """Request program meta information."""
        raise NotImplementedError

    def run(self, context: ProgramContext) -> Dict[str, Any]:
        """Run the program.

        :param context: The context objects for the Program. The context objects are specific for a node.
        :return: A dictionary of outputs desired for postprocessing.
        """
        raise NotImplementedError
