import threading
from multiprocessing.pool import ThreadPool
from typing import Any, Dict, Optional

import netsquid as ns
from netqasm.lang.instr.flavour import NVFlavour, VanillaFlavour
from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import reset_struct_loggers, save_all_struct_loggers
from netqasm.runtime.app_config import AppConfig
from netqasm.runtime.application import ApplicationInstance
from netqasm.runtime.interface.config import NetworkConfig, QuantumHardware
from netqasm.runtime.runtime_mgr import RuntimeManager
from netqasm.sdk.classical_communication import reset_socket_hub
from netqasm.sdk.classical_communication.thread_socket.socket import ThreadSocket
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.nodes.node import Node as NetSquidNode

from squidasm.nqasm.netstack import NetworkStack
from squidasm.nqasm.qnodeos import SubroutineHandler
from squidasm.sim.glob import pop_current_backend, put_current_backend
from squidasm.sim.network import reset_network
from squidasm.sim.network.network import NetSquidNetwork
from squidasm.sim.network.nv_config import NVConfig
from squidasm.sim.queues import QueueManager
from squidasm.util.thread import as_completed

_logger = get_netqasm_logger()


class SquidAsmRuntimeManager(RuntimeManager):
    _SUBROUTINE_HANDLER_CLASS = SubroutineHandler
    _NETWORK_STACK_CLASS = NetworkStack

    def __init__(self):
        self._network_instance: Optional[NetSquidNetwork] = None
        self._netsquid_formalism: ns.QFormalism = ns.QFormalism.KET
        self._subroutine_handlers: Dict[str, SubroutineHandler] = dict()
        self._is_running: bool = False
        self._party_map: Dict[str, NetSquidNode] = dict()
        self._backend_thread = None
        self._backend_log_dir: Optional[str] = None

        self.reset_backend()

    @property
    def network(self) -> Optional[NetSquidNetwork]:
        return self._network_instance

    @property
    def nodes(self) -> Dict[str, NetSquidNode]:
        assert self.network is not None
        return self.network.nodes  # type: ignore

    @property
    def netsquid_formalism(self) -> ns.QFormalism:
        return self._netsquid_formalism

    @netsquid_formalism.setter
    def netsquid_formalism(self, formalism):
        self._netsquid_formalism = formalism

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def backend_log_dir(self) -> Optional[str]:
        return self._backend_log_dir

    @backend_log_dir.setter
    def backend_log_dir(self, new_dir: str) -> None:
        self._backend_log_dir = new_dir
        for handler in self.subroutine_handlers.values():
            handler._executor.set_instr_logger(new_dir)
        assert self._network_instance is not None
        self._network_instance.set_logger(new_dir)

    @property
    def party_map(self) -> Dict[str, NetSquidNode]:
        return self._party_map

    # TODO rename
    @property
    def app_node_map(self) -> Dict[str, NetSquidNode]:
        return self._party_map

    @property
    def subroutine_handlers(self):
        return self._subroutine_handlers

    @property
    def qmemories(self):
        return {node_name: node.qmemory for node_name, node in self.nodes.items()}

    @property
    def executors(self):
        return {
            node_name: subroutine_handler._executor
            for node_name, subroutine_handler in self.subroutine_handlers.items()
        }

    def start_backend(self) -> None:
        if self._backend_thread:
            _logger.error("Already a backend running")
            return

        def backend_thread(manager):
            _logger.debug("Starting netsquid backend")
            if self.network is None:
                _logger.warning(
                    "Trying to start backend but no Network Instance exists"
                )
                return

            ns.set_qstate_formalism(self.netsquid_formalism)

            for subroutine_handler in self._subroutine_handlers.values():
                subroutine_handler.start()

            self._is_running = True
            _logger.info(
                "\n-------------\nStarting NetSquid simulator\n-------------\n"
            )
            put_current_backend(self)
            ns.sim_run()
            pop_current_backend()
            _logger.info(
                "\n-------------\nNetSquid simulator finished\n-------------\n"
            )
            self._is_running = False

        t = threading.Thread(target=backend_thread, args=(self,))
        self._backend_thread = t
        t.start()

    def stop_backend(self):
        for subroutine_handler in self._subroutine_handlers.values():
            subroutine_handler.stop()
        self._backend_thread.join()
        self._backend_thread = None
        SharedMemoryManager.reset_memories()
        QueueManager.destroy_queues()
        reset_network()
        reset_socket_hub()
        reset_struct_loggers()

    def reset_backend(self, save_loggers=False):
        if save_loggers:
            save_all_struct_loggers()
        ns.sim_reset()
        SharedMemoryManager.reset_memories()
        reset_network()
        QueueManager.reset_queues()
        reset_socket_hub()
        reset_struct_loggers()

    def set_network(
        self, cfg: NetworkConfig, nv_cfg: Optional[NVConfig] = None
    ) -> None:
        network = NetSquidNetwork(
            network_config=cfg,
            nv_config=nv_cfg,
            global_log_dir=self.backend_log_dir,  # TODO
        )
        self._network_instance = network
        self._create_subroutine_handlers()

    def run_app(
        self,
        app_instance: ApplicationInstance,
        use_app_config=True,
        save_loggers=True,
    ) -> Dict[str, Any]:
        assert self.network is not None

        programs = app_instance.app.programs

        for party, node_name in app_instance.party_alloc.items():
            self._party_map[party] = self.network.get_node(node_name)

        with ThreadPool(len(programs) + 1) as executor:
            # Start the program threads
            program_futures = []
            for program in programs:
                inputs = app_instance.program_inputs[program.party]
                if use_app_config:
                    app_cfg = AppConfig(
                        app_name=program.party,
                        node_name=self._party_map[program.party],
                        main_func=program.entry,
                        log_config=app_instance.logging_cfg,
                        inputs=inputs,
                    )
                    inputs["app_config"] = app_cfg
                future = executor.apply_async(program.entry, kwds=inputs)
                program_futures.append(future)

            # Join the application threads and the backend
            program_names = [program.party for program in app_instance.app.programs]
            # NOTE: use app_<name> instead of prog_<name> for now for backward compatibility
            names = [f"app_{prog_name}" for prog_name in program_names]
            results = {}
            for future, name in as_completed(program_futures, names=names):
                results[name] = future.get()

            if save_loggers:
                save_all_struct_loggers()
            reset_struct_loggers()
            reset_socket_hub()
            ThreadSocket._COMM_LOGGERS = {}

            return results

    def _create_subroutine_handlers(self):
        self._subroutine_handlers: Dict[str, SubroutineHandler] = dict()

        ll_services = self.network.link_layer_services

        # Create subroutine handlers for each node in the network.
        for node in self.network.nodes.values():
            node_hardware = self.network.node_hardware_types[node.name]
            if node_hardware == QuantumHardware.NV:
                flavour = NVFlavour()
            elif node_hardware == QuantumHardware.Generic:
                flavour = VanillaFlavour()
            else:
                raise ValueError(f"Quantum hardware {node_hardware} not supported.")

            subroutine_handler = self.__class__._SUBROUTINE_HANDLER_CLASS(
                node=node,
                instr_log_dir=self._backend_log_dir,  # TODO
                flavour=flavour,
                instr_proc_time=self.network.instr_proc_time,
                host_latency=self.network.host_latency,
            )
            subroutine_handler.network_stack = self.__class__._NETWORK_STACK_CLASS(
                node=node, link_layer_services=ll_services[node.name]
            )
            reaction_handler = subroutine_handler.get_epr_reaction_handler()
            for service in ll_services[node.name].values():
                service.add_reaction_handler(reaction_handler)

            self._subroutine_handlers[node.name] = subroutine_handler
