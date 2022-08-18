from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Generator, Optional

from netqasm.backend.messages import SubroutineMessage
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.connection import T_Message
from netqasm.sdk.shared_memory import SharedMemory

from pydynaa import EventExpression

if TYPE_CHECKING:
    from squidasm.qoala.sim.host import Host

from squidasm.qoala.sim.common import LogManager


class QnosConnection:
    def __init__(
        self,
        host: Host,
        app_id: int,
        app_name: str,
        max_qubits: int = 5,
        **kwargs,
    ) -> None:
        self._app_name = app_name
        self._app_id = app_id
        self._node_name = app_name
        self._max_qubits = max_qubits

        self._host = host

        self._shared_memory = None
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._app_name})"
        )

    @property
    def shared_memory(self) -> SharedMemory:
        return self._shared_memory

    def _commit_message(
        self, msg: T_Message, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        assert isinstance(msg, SubroutineMessage)
        self._logger.debug(f"Committing message {msg}")
        self._host.send_qnos_msg(bytes(msg))

    def commit_subroutine(
        self,
        subroutine: Subroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> Generator[EventExpression, None, None]:
        self._logger.info(f"Commiting compiled subroutine:\n{subroutine}")

        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

        result = yield from self._host.receive_qnos_msg()
        self._shared_memory = result
