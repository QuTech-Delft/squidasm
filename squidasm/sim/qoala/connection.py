from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Generator, Optional, Type

from netqasm.backend.messages import SubroutineMessage
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.build_types import GenericHardwareConfig, HardwareConfig
from netqasm.sdk.builder import Builder
from netqasm.sdk.connection import (
    BaseNetQASMConnection,
    NetworkInfo,
    ProtoSubroutine,
    T_Message,
)
from netqasm.sdk.shared_memory import SharedMemory

from pydynaa import EventExpression

if TYPE_CHECKING:
    from netqasm.sdk.transpile import SubroutineTranspiler
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
        hardware_config: Optional[HardwareConfig] = None,
        compiler: Optional[Type[SubroutineTranspiler]] = None,
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

        if hardware_config is None:
            hardware_config = GenericHardwareConfig(max_qubits)

        self._builder = Builder(
            connection=self,
            app_id=self._app_id,
            hardware_config=hardware_config,
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

    def commit_protosubroutine(
        self,
        protosubroutine: ProtoSubroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> Generator[EventExpression, None, None]:
        self._logger.info(f"Flushing protosubroutine:\n{protosubroutine}")

        subroutine = self._builder.subrt_compile_subroutine(protosubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        yield from self.commit_subroutine(subroutine, block, callback)
        self._builder._reset()

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

    def flush(
        self, block: bool = True, callback: Optional[Callable] = None
    ) -> Generator[EventExpression, None, None]:
        subroutine = self._builder.subrt_pop_pending_subroutine()
        if subroutine is None:
            return

        yield from self.commit_protosubroutine(
            protosubroutine=subroutine,
            block=block,
            callback=callback,
        )

    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        pass

    def _get_network_info(self) -> Type[NetworkInfo]:
        return NetSquidNetworkInfo
