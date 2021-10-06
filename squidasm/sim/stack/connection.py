from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Generator, Optional, Type

from netqasm.backend.messages import SubroutineMessage
from netqasm.sdk.builder import Builder
from netqasm.sdk.connection import (
    BaseNetQASMConnection,
    NetworkInfo,
    PreSubroutine,
    T_Message,
)
from netqasm.sdk.shared_memory import SharedMemory

from pydynaa import EventExpression

if TYPE_CHECKING:
    from netqasm.sdk.compiling import SubroutineCompiler
    from squidasm.sim.stack.host import Host

from squidasm.sim.stack.common import LogManager

from .context import NetSquidNetworkInfo


class QnosConnection(BaseNetQASMConnection):
    def __init__(
        self,
        host: Host,
        app_id: int,
        app_name: str,
        max_qubits: int = 5,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        **kwargs,
    ) -> None:
        self._app_name = app_name
        self._app_id = app_id
        self._node_name = app_name
        self._max_qubits = max_qubits

        self._host = host

        self._shared_memory = None
        self._logger: logging.Logger = LogManager.get_stack_logger(
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
        return self._shared_memory

    def __enter__(self) -> QnosConnection:
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()

    def _commit_message(
        self, msg: T_Message, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        assert isinstance(msg, SubroutineMessage)
        self._logger.debug(f"Committing message {msg}")
        self._host.send_qnos_msg(bytes(msg))

    def commit_subroutine(
        self,
        presubroutine: PreSubroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> Generator[EventExpression, None, None]:
        self._logger.info(f"Flushing presubroutine:\n{presubroutine}")

        subroutine = self._builder._pre_process_subroutine(presubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

        result = yield from self._host.receive_qnos_msg()
        self._shared_memory = result

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
