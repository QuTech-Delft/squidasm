from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, Generator, List, Optional, Type

from netqasm.backend.messages import (
    InitNewAppMessage,
    OpenEPRSocketMessage,
    StopAppMessage,
    SubroutineMessage,
)
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.builder import Builder
from netqasm.sdk.connection import (
    BaseNetQASMConnection,
    NetworkInfo,
    PreSubroutine,
    T_Message,
)
from netqasm.sdk.shared_memory import SharedMemory

from pydynaa import EventExpression
from squidasm.run.singlethread.context import NetSquidContext
from squidasm.run.singlethread.protocols import (
    SUBRT_FINISHED,
    HostProtocol,
    NewResultEvent,
)

if TYPE_CHECKING:
    from netqasm.sdk.compiling import SubroutineCompiler
    from netqasm.sdk.epr_socket import EPRSocket

from squidasm.run.singlethread.context import NetSquidNetworkInfo


class NetSquidConnection(BaseNetQASMConnection):
    def __init__(
        self,
        app_name: str,
        max_qubits: int = 5,
        epr_sockets: Optional[List[EPRSocket]] = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        **kwargs,
    ) -> None:
        self._app_name = app_name
        self._app_id = 0
        self._node_name = app_name
        self._max_qubits = max_qubits
        self._epr_sockets = [] if epr_sockets is None else epr_sockets

        self._protocol: HostProtocol = NetSquidContext.get_protocols()[app_name]

        self._epr_sck_status: Dict[EPRSocket, bool] = {
            sck: False for sck in self._epr_sockets
        }
        for sck in self._epr_sockets:
            sck.conn = self

        self._shared_memory = None
        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self.app_name})"
        )

        self._builder = Builder(
            connection=self,
            app_id=self._app_id,
            max_qubits=max_qubits,
            compiler=compiler,
        )

    @property
    def shared_memory(self) -> SharedMemory:
        return self._protocol._qnodeos.executor._shared_memories[0]

    def __enter__(self) -> NetSquidConnection:
        self._commit_message(
            msg=InitNewAppMessage(
                app_id=0,
                max_qubits=self._max_qubits,
            )
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self, clear_app: bool = True, stop_backend: bool = False) -> None:
        self.flush()
        self._commit_message(StopAppMessage(self._app_id))

    def _wait_for_results(self) -> Generator[EventExpression, None, None]:
        if len(self._protocol.results_listener.buffer) == 0:
            yield EventExpression(
                source=self._protocol.results_listener, event_type=NewResultEvent
            )

        msg = self._protocol.results_listener.buffer.pop(0)
        assert msg == SUBRT_FINISHED

    def _commit_message(
        self, msg: T_Message, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        self._logger.debug(f"Committing message {msg}")
        self._protocol.qnos_port.tx_output(bytes(msg))

    def _commit_open_epr_socket(
        self, sck: EPRSocket
    ) -> Generator[EventExpression, None, None]:
        self._commit_message(
            OpenEPRSocketMessage(
                app_id=self._app_id,
                epr_socket_id=sck.epr_socket_id,
                remote_node_id=sck.remote_node_id,
                remote_epr_socket_id=sck.remote_epr_socket_id,
                min_fidelity=sck.min_fidelity,
            )
        )
        yield from self._wait_for_results()

    def commit_subroutine(
        self,
        presubroutine: PreSubroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> Generator[EventExpression, None, None]:
        for sck, opened in self._epr_sck_status.items():
            if not opened:
                yield from self._commit_open_epr_socket(sck)
                self._epr_sck_status[sck] = True

        self._logger.debug(f"Flushing presubroutine:\n{presubroutine}")

        subroutine = self._builder._pre_process_subroutine(presubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

        yield from self._wait_for_results()

        self._builder._reset()

    def flush(
        self, block: bool = True, callback: Optional[Callable] = None
    ) -> Generator[EventExpression, None, None]:
        subroutine = self._builder._pop_pending_subroutine()
        if subroutine is None:
            return

        yield from self.commit_subroutine(
            presubroutine=subroutine,
            block=block,
            callback=callback,
        )

    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        pass

    def _get_network_info(self) -> Type[NetworkInfo]:
        return NetSquidNetworkInfo
