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
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.eprsocket import EprSocket
from squidasm.qoala.sim.host import Host
from squidasm.qoala.sim.hostcomp import HostComponent
from squidasm.qoala.sim.memory import ProgramMemory, UnitModule
from squidasm.qoala.sim.netstack import Netstack, NetstackComponent
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnodecomp import ProcNodeComponent
from squidasm.qoala.sim.qdevice import (
    NVPhysicalQuantumMemory,
    PhysicalQuantumMemory,
    QDevice,
    QDeviceType,
)
from squidasm.qoala.sim.qnos import Qnos
from squidasm.qoala.sim.qnoscomp import QnosComponent
from squidasm.qoala.sim.scheduler import Scheduler, SchedulerComponent


class ProcNode(Protocol):
    """NetSquid protocol representing a node with a software stack.

    The software stack consists of a Scheduler, Host, QNodeOS and a QDevice.
    The Host and QNodeOS are each represented by separate subprotocols.
    The QDevice is handled/modeled as part of the QNodeOS protocol.
    """

    def __init__(
        self,
        name: str,
        global_env: GlobalEnvironment,
        qprocessor: QuantumProcessor,
        node: Optional[ProcNodeComponent] = None,
        qdevice_type: Optional[str] = "generic",
        node_id: Optional[int] = None,
        use_default_components: bool = True,
    ) -> None:
        """ProcNode constructor.

        :param name: name of this node
        :param node: an existing ProcNodeComponent object containing the static
            components or None. If None, a ProcNodeComponent is automatically
            created.
        :param qdevice_type: hardware type of the QDevice, defaults to "generic"
        :param qdevice: NetSquid `QuantumProcessor` representing the QDevice,
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

        self._host: Optional[Host] = None
        self._qnos: Optional[Qnos] = None
        self._netstack: Optional[Netstack] = None
        self._scheduler: Optional[Scheduler] = None

        # Create internal components.
        # If `use_default_components` is False, these components must be manually
        # created and added to this ProcNode.
        if use_default_components:
            self._scheduler = Scheduler(self._node.name)
            self._host = Host(self.host_comp, self._local_env, self.scheduler)
            self._qnos = Qnos(
                self.qnos_comp, self._local_env, self.scheduler, self.qdevice
            )
            self._nestack = Netstack(
                self.netstack_comp, self._local_env, self.scheduler, self.qdevice
            )

        self._qdevice: QDevice
        if qdevice_type == "generic":
            physical_memory = PhysicalQuantumMemory(qprocessor.num_positions)
            self._qdevice = QDevice(self._node, QDeviceType.GENERIC, physical_memory)
        elif qdevice_type == "nv":
            physical_memory = NVPhysicalQuantumMemory(qprocessor.num_positions)
            self._qdevice = QDevice(self._node, QDeviceType.NV, physical_memory)
        else:
            raise ValueError

        self._prog_instance_counter: int = 0
        self._batch_counter: int = 0
        self._batches: Dict[int, ProgramBatch] = {}  # batch ID -> batch

        self._prog_results: Dict[int, ProgramResult] = {}  # program ID -> result
        self._batch_result: Dict[int, BatchResult] = {}  # batch ID -> result

    def install_environment(self) -> None:
        self._scheduler.install_schedule(self._local_env._local_schedule)
        for instance in self._local_env._programs:
            self._scheduler.init_new_program(instance)

    def assign_ll_protocol(
        self, remote_id: int, prot: MagicLinkLayerProtocolWithSignaling
    ) -> None:
        """Set the link layer protocol to use for entanglement generation.

        The same link layer protocol object is used by both nodes sharing a link in
        the network."""
        self.qnos.assign_ll_protocol(remote_id, prot)

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
    def scheduler_comp(self) -> SchedulerComponent:
        return self.node.scheduler_comp

    @property
    def qdevice(self) -> QDevice:
        return self.node.qdevice

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
    def scheduler(self) -> Scheduler:
        return self._scheduler

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
        self.node.qnos_peer_out_port(there).connect(other.node.qnos_peer_in_port(here))
        self.node.qnos_peer_in_port(there).connect(other.node.qnos_peer_out_port(here))

    def start(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        # assert self._net is not None
        super().start()
        self._scheduler.start()
        self._host.start()
        self._qnos.start()

    def stop(self) -> None:
        assert self._host is not None
        assert self._qnos is not None
        self._qnos.stop()
        self._host.stop()
        self._scheduler.stop()
        super().stop()

    def submit_batch(self, batch_info: BatchInfo) -> None:
        prog_instances: List[ProgramInstance] = []

        for input in batch_info.inputs:
            instance = ProgramInstance(
                pid=self._prog_instance_counter,
                program=batch_info.program,
                inputs=input,
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
                    prog_instance.pid, unit_module=UnitModule.default_generic()
                )
                meta = prog_instance.program.meta

                csockets: Dict[int, ClassicalSocket] = {}
                for i, remote_name in meta.csockets:
                    csockets[i] = self.host.create_csocket(remote_name)

                epr_sockets: Dict[int, EprSocket] = {}
                for i, remote_name in meta.epr_sockets:
                    remote_id = self._global_env.get_node_id(remote_name)
                    epr_sockets[i] = EprSocket(i, remote_id)

                result = ProgramResult(values={})

                process = IqoalaProcess(
                    prog_instance=prog_instance,
                    prog_memory=prog_memory,
                    csockets=csockets,
                    epr_sockets=epr_sockets,
                    subroutines={},
                    result=result,
                )

                self.host.add_process(process)
                self.qnos.add_process(process)
