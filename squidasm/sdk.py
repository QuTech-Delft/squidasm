from threading import Thread
from typing import Type

from netqasm.lang.subroutine import PreSubroutine, Subroutine
from netqasm.lang.parsing.text import assemble_subroutine
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.network import NetworkInfo

from squidasm.queues import get_queue
from squidasm.backend.glob import (
    get_node_id_for_app,
    get_node_name_for_app,
    get_node_name,
    get_node_id,
    get_running_backend
)


class NetSquidConnection(BaseNetQASMConnection):

    def __init__(
        self,
        app_name,
        app_id=None,
        max_qubits=5,
        log_config=None,
        epr_sockets=None,
        compiler=None,
    ):
        node_name = get_node_name_for_app(app_name)
        self._message_queue = get_queue(node_name)
        super().__init__(
            app_name=app_name,
            node_name=node_name,
            app_id=app_id,
            max_qubits=max_qubits,
            log_config=log_config,
            epr_sockets=epr_sockets,
            compiler=compiler,
        )

    def _get_network_info(self) -> Type[NetworkInfo]:
        return NetSquidNetworkInfo

    def _commit_serialized_message(self, raw_msg, block=True, callback=None):
        """Commit a message to the backend/qnodeos"""
        self._message_queue.put(raw_msg)
        if block:
            self._execute_callback(item=raw_msg, callback=callback)
        else:
            # Execute callback in a new thread after the subroutine is finished
            thread = Thread(target=self._execute_callback, args=(raw_msg, callback,))
            thread.daemon = True
            thread.start()

    def _execute_callback(self, item, callback=None):
        self.block(item=item)
        if callback is not None:
            callback()

    def block(self, item=None):
        """Block until flushed subroutines finish"""
        if item is None:
            self._message_queue.join()
        else:
            self._message_queue.join_task(item=item)

    def _pre_process_subroutine(self, pre_subroutine: PreSubroutine) -> Subroutine:
        """Parses and assembles the subroutine.
        """
        subroutine: Subroutine = assemble_subroutine(pre_subroutine)
        if self._compiler is not None:
            subroutine = self._compiler(subroutine=subroutine).compile()
        else:
            backend = get_running_backend()
            subroutine_handler = backend.subroutine_handlers[self.node_name]
            flavour = subroutine_handler.flavour
            if isinstance(flavour, NVFlavour):
                self._logger.info("Compiling subroutine to NV flavour")
                subroutine = NVSubroutineCompiler(subroutine=subroutine).compile()

        if self._track_lines:
            self._log_subroutine(subroutine=subroutine)
        return subroutine


class NetSquidNetworkInfo(NetworkInfo):
    @classmethod
    def _get_node_id(cls, node_name):
        """Returns the node id for the node with the given name"""
        return get_node_id(name=node_name)

    @classmethod
    def _get_node_name(cls, node_id):
        """Returns the node name for the node with the given ID"""
        return get_node_name(node_id=node_id)

    @classmethod
    def get_node_id_for_app(cls, app_name):
        """Returns the node id for the app with the given name"""
        return get_node_id_for_app(app_name=app_name)

    @classmethod
    def get_node_name_for_app(cls, app_name):
        """Returns the node name for the app with the given name"""
        return get_node_name_for_app(app_name=app_name)
