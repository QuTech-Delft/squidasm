from __future__ import annotations

from typing import Dict, List, Optional

from netsquid.components import QuantumProcessor
from netsquid.protocols import Protocol
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling

from squidasm.qoala.runtime.environment import GlobalEnvironment, LocalEnvironment
from squidasm.qoala.runtime.program import (
    BatchInfo,
    BatchResult,
    ProgramBatch,
    ProgramInstance,
    ProgramResult,
)
from squidasm.qoala.runtime.schedule import ProgramTaskList, Schedule
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.egpmgr import EgpManager
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.memmgr import MemoryManager
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnodecomp import ProcNodeComponent
from squidasm.qoala.sim.qdevice import (
    GenericPhysicalQuantumMemory,
    NVPhysicalQuantumMemory,
    QDevice,
    QDeviceType,
)
from squidasm.qoala.sim.qnos import Qnos
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.scheduler import Scheduler


class ProcNode(Protocol):
    """NetSquid protocol representing a node with a software stack."""

    def __init__(
        self,
        name: str,
        global_env: GlobalEnvironment,
        qprocessor: QuantumProcessor,
        node: Optional[ProcNodeComponent] = None,
        qdevice_type: Optional[str] = "generic",
        node_id: Optional[int] = None,
        scheduler: Optional[Scheduler] = None,
        asynchronous: bool = False,
    ) -> None:
        """ProcNode constructor.

        :param name: name of this node
        :param node: an existing ProcNodeComponent object containing the static
            components or None. If None, a ProcNodeComponent is automatically
            created.
        :param qdevice_type: hardware type of the QDevice, defaults to "generic"
        :param qprocessor: NetSquid `QuantumProcessor` representing the QDevice,
            defaults to None. If None, a QuantumProcessor is created
            automatically.
        :param node_id: ID to use for the internal NetSquid node object
        :param use_default_components: whether to automatically create NetSquid
            components for the Host and QNodeOS, defaults to True. If False,
            this allows for manually creating and adding these components.
        """
        super().__init__(name=f"{name}")
        if node:
            self._node = node
        else:
            self._node = ProcNodeComponent(name, qprocessor, global_env, node_id)

        self._global_env = global_env
        self._local_env = LocalEnvironment(global_env, global_env.get_node_id(name))
        self._asynchronous = asynchronous

        # Create internal components.
        self._qdevice: QDevice
        if qdevice_type == "generic":
            physical_memory = GenericPhysicalQuantumMemory(qprocessor.num_positions)
            self._qdevice = QDevice(self._node, QDeviceType.GENERIC, physical_memory)
        elif qdevice_type == "nv":
            physical_memory = NVPhysicalQuantumMemory(qprocessor.num_positions)
            self._qdevice = QDevice(self._node, QDeviceType.NV, physical_memory)
        else:
            raise ValueError

        self._host = Host(self.host_comp, self._local_env, self._asynchronous)
        self._memmgr = MemoryManager(self.node.name, self._qdevice)
        self._egpmgr = EgpManager()
        self._qnos = Qnos(
            self.qnos_comp,
            self._local_env,
            self._memmgr,
            self._qdevice,
            self._asynchronous,
        )
        self._netstack = Netstack(
            self.netstack_comp,
            self._local_env,
            self._memmgr,
            self._egpmgr,
            self._qdevice,
        )

        if scheduler is None:
            self._scheduler = Scheduler(
                self._node.name, self._host, self._qnos, self._netstack, self._memmgr
            )
        else:
            self._scheduler = scheduler

        self._prog_instance_counter: int = 0
        self._batch_counter: int = 0
        self._batches: Dict[int, ProgramBatch] = {}  # batch ID -> batch

        self._prog_results: Dict[int, ProgramResult] = {}  # program ID -> result
        self._batch_result: Dict[int, BatchResult] = {}  # batch ID -> result

    def install_environment(self) -> None:
        self._scheduler.install_schedule(self._local_env._local_schedule)
        for instance in self._local_env._programs:
            self._scheduler.init_new_program(instance)

    def install_schedule(self, schedule: Schedule) -> None:
        self.scheduler.install_schedule(schedule)

    def assign_ll_protocol(
        self, remote_id: int, prot: MagicLinkLayerProtocolWithSignaling
    ) -> None:
        """Set the link layer protocol to use for entanglement generation.

        The same link layer protocol object is used by both nodes sharing a link in
        the network."""
        self._egpmgr.add_egp(remote_id, EgpProtocol(self.node, prot))

    @property
    def node(self) -> ProcNodeComponent:
        return self._node

    @property
    def host_comp(self) -> HostComponent:
        return self.node.host_comp

    @property
    def qnos_comp(self) -> QnosComponent:
        return self.node.qnos_comp

    @property
    def netstack_comp(self) -> NetstackComponent:
        return self.node.netstack_comp

    @property
    def qdevice(self) -> QDevice:
        return self._qdevice

    @qdevice.setter
    def qdevice(self, qdevice) -> QDevice:
        self._qdevice = qdevice
        self.qnos.qdevice = qdevice
        self.netstack.qdevice = qdevice

    @property
    def host(self) -> Host:
        return self._host

    @host.setter
    def host(self, host: Host) -> None:
        self._host = host

    @property
    def qnos(self) -> Qnos:
        return self._qnos

    @qnos.setter
    def qnos(self, qnos: Qnos) -> None:
        self._qnos = qnos

    @property
    def netstack(self) -> Netstack:
        return self._netstack

    @netstack.setter
    def netstack(self, netstack: Netstack) -> None:
        self._netstack = netstack

    @property
    def scheduler(self) -> Scheduler:
        return self._scheduler

    @property
    def memmgr(self) -> MemoryManager:
        return self._memmgr

    @property
    def egpmgr(self) -> EgpManager:
        return self._egpmgr

    @scheduler.setter
    def scheduler(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def connect_to(self, other: ProcNode) -> None:
        """Create connections between ports of this ProcNode and those of
        another ProcNode."""
        here = self.node.name
        there = other.node.name
        self.node.host_peer_out_port(there).connect(other.node.host_peer_in_port(here))
        self.node.host_peer_in_port(there).connect(other.node.host_peer_out_port(here))
        self.node.netstack_peer_out_port(there).connect(
            other.node.netstack_peer_in_port(here)
        )
        self.node.netstack_peer_in_port(there).connect(
            other.node.netstack_peer_out_port(here)
        )

    def start(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        assert self._netstack is not None
        super().start()
        self._host.start()
        self._qnos.start()
        self._netstack.start()
        self._scheduler.start()

    def stop(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        assert self._netstack is not None
        self._scheduler.stop()
        self._netstack.stop()
        self._qnos.stop()
        self._host.stop()
        super().stop()

    def submit_batch(self, batch_info: BatchInfo) -> None:
        prog_instances: List[ProgramInstance] = []

        for input in batch_info.inputs:
            instance = ProgramInstance(
                pid=self._prog_instance_counter,
                program=batch_info.program,
                inputs=input,
                tasks=batch_info.tasks,
            )
            self._prog_instance_counter += 1
            prog_instances.append(instance)

        batch = ProgramBatch(
            batch_id=self._batch_counter, info=batch_info, instances=prog_instances
        )
        self._batches[batch.batch_id] = batch
        self._batch_counter += 1

    def initialize_runtime(self) -> None:
        for batch in self._batches.values():
            for prog_instance in batch.instances:
                prog_memory = ProgramMemory(
                    prog_instance.pid,
                    unit_module=UnitModule.default_generic(batch.info.num_qubits),
                )
                meta = prog_instance.program.meta

                csockets: Dict[int, ClassicalSocket] = {}
                for i, remote_name in meta.csockets.items():
                    # TODO: check for already existing epr sockets
                    csockets[i] = self.host.create_csocket(remote_name)

                epr_sockets: Dict[int, EprSocket] = {}
                for i, remote_name in meta.epr_sockets.items():
                    remote_id = self._global_env.get_node_id(remote_name)
                    # TODO: check for already existing epr sockets
                    # TODO: fidelity
                    epr_sockets[i] = EprSocket(i, remote_id, 1.0)

                result = ProgramResult(values={})

                process = IqoalaProcess(
                    prog_instance=prog_instance,
                    prog_memory=prog_memory,
                    csockets=csockets,
                    epr_sockets=epr_sockets,
                    subroutines={},
                    requests={},
                    result=result,
                )

                self.add_process(process)
                self.scheduler.initialize(process)

    def add_process(self, process: IqoalaProcess) -> None:
        self.memmgr.add_process(process)
