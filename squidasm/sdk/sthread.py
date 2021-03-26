from __future__ import annotations

from threading import Thread
from typing import TYPE_CHECKING, Callable, List, Optional, Type

from netqasm.backend.executor import Executor
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.components.component import Port

from squidasm.glob import (
    get_node_id,
    get_node_id_for_app,
    get_node_name,
    get_node_name_for_app,
    get_running_backend,
)
from squidasm.interface.queues import QueueManager

from .sdk import NetSquidNetworkInfo

if TYPE_CHECKING:
    from netqasm.sdk.compiling import SubroutineCompiler
    from netqasm.sdk.config import LogConfig
    from netqasm.sdk.epr_socket import EPRSocket

    from squidasm.interface.queues import TaskQueue


class SThreadNetSquidConnection(BaseNetQASMConnection):
    def __init__(
        self,
        app_name: str,
        qnos_port: Port,
        executor: Executor,
        app_id: Optional[int] = None,
        max_qubits: int = 5,
        log_config: LogConfig = None,
        epr_sockets: Optional[List[EPRSocket]] = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        return_arrays: bool = True,
        **kwargs,
    ) -> None:
        node_name = app_name
        self._qnos_port = qnos_port
        self._executor = executor

        assert compiler is not None

        super().__init__(
            app_name=app_name,
            node_name=node_name,
            app_id=app_id,
            max_qubits=max_qubits,
            log_config=log_config,
            epr_sockets=epr_sockets,
            compiler=compiler,
            return_arrays=return_arrays,
            _init_app=False,
            _setup_epr_sockets=False,
        )

        self._clear_app_on_exit: bool = False
        self._stop_backend_on_exit: bool = False

    def _get_network_info(self) -> Type[NetworkInfo]:
        return NetSquidNetworkInfo

    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        self._qnos_port.tx_output(raw_msg)

    @property
    def shared_memory(self) -> SharedMemory:
        if self._shared_memory is None:
            mem = SharedMemoryManager.get_shared_memory(
                self.node_name, key=self._app_id
            )
            self._shared_memory = mem
        return self._shared_memory
