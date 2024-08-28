import copy
import os
from typing import Dict, List, Optional, Tuple

import netsquid as ns
import numpy as np
from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import NetworkLogger
from netqasm.qlink_compat import RequestType
from netqasm.runtime.interface.config import (
    Link,
    NetworkConfig,
    NoiseType,
    QuantumHardware,
)
from netqasm.runtime.interface.logging import EntanglementStage
from netsquid.components import PhysicalInstruction, QuantumProcessor
from netsquid.components import instructions as ns_instructions
from netsquid.components.models.qerrormodels import DepolarNoiseModel, T1T2NoiseModel
from netsquid.components.qmemory import MemPositionBusyError
from netsquid.nodes import Network, Node
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits.state_sampler import StateSampler
from netsquid.util import sim_time
from netsquid_magic.link_layer import (
    LinkLayerService,
    MagicLinkLayerProtocol,
    SingleClickTranslationUnit,
    TranslationUnit,
)
from netsquid_magic.magic_distributor import (
    BitflipMagicDistributor,
    DepolariseMagicDistributor,
    MagicDistributor,
    PerfectStateMagicDistributor,
)
from netsquid_magic.model_parameters import (
    BitFlipModelParameters,
    DepolariseModelParameters,
    PerfectModelParameters,
)
from netsquid_magic.state_delivery_sampler import HeraldedStateDeliverySamplerFactory
from qlink_interface import (
    ReqCreateAndKeep,
    ReqMeasureDirectly,
    ResCreateAndKeep,
    ResMeasureDirectly,
)

from pydynaa import EventType
from squidasm.sim.glob import QubitInfo, get_running_backend
from squidasm.sim.network.nv_config import NVConfig, build_nv_qdevice

T_SingleQubitState = Tuple[Tuple[np.complex, np.complex]]

EprDeliveredEvent: EventType = EventType(
    "EPR_DELIVERED",
    "Event that an EPR has been delivered by a Distributor, and hence Executors "
    "can start looking at their updated Array values",
)


logger = get_netqasm_logger()


class NetSquidNetwork(Network):
    """
    Represents the collection of nodes and links in the simulated network.

    The constructor creates Nodes based on the given NetworkConfig,
    and creates link layer services for each pair of connected nodes.
    """

    def __init__(
        self,
        network_config: NetworkConfig,
        nv_config: Optional[NVConfig] = None,
        global_log_dir: Optional[str] = None,
    ) -> None:
        self._global_logger: NetworkLogger
        if global_log_dir is not None:
            logger_path = os.path.join(global_log_dir, "network_log.yaml")
            self._global_logger = NetworkLogger(logger_path)
        else:
            self._global_logger = None

        self._network_config: NetworkConfig = network_config
        self._nv_config: Optional[NVConfig] = nv_config
        self._node_hardware_types: Dict[str, QuantumHardware] = {}

        self._instr_proc_time: int
        self._host_latency: int
        if nv_config is not None:
            self._instr_proc_time = nv_config.instr_proc_time
            self._host_latency = nv_config.host_latency
        else:
            self._instr_proc_time = 0
            self._host_latency = 0

        # create NetSquid `Node`s and add them to this `Network`
        self._build_network()

        self._link_layer_services: Dict[str, Dict[int, LinkLayerService]] = dict()
        self._create_link_layer_services()

    # TODO: set_log_directory()
    def set_logger(self, log_dir: str):
        logger_path = os.path.join(log_dir, "network_log.yaml")
        self._global_logger = NetworkLogger(logger_path)

    @property
    def instr_proc_time(self) -> int:
        return self._instr_proc_time

    @property
    def host_latency(self) -> int:
        return self._host_latency

    @property
    def node_hardware_types(self) -> Dict[str, QuantumHardware]:
        return self._node_hardware_types

    @property
    def link_layer_services(self) -> Dict[str, Dict[int, LinkLayerService]]:
        return self._link_layer_services

    def global_log(self, *args, **kwargs) -> None:
        if self._global_logger is not None:
            self._global_logger.log(*args, **kwargs)

    def _build_network(self) -> None:
        for i, node_cfg in enumerate(self._network_config.nodes):
            try:
                hardware = QuantumHardware(node_cfg.hardware)
            except Exception:
                logger.warn("Hardware type not valid. Using a generic one.")
                hardware = QuantumHardware.Generic
            self._node_hardware_types[node_cfg.name] = hardware

            mem_fidelities = [T1T2NoiseModel(q.t1, q.t2) for q in node_cfg.qubits]

            if hardware == QuantumHardware.NV:
                if self._nv_config is None:
                    qdevice = NVQDevice(
                        name=f"{node_cfg.name}_NVQDevice",
                        num_qubits=len(node_cfg.qubits),
                        gate_fidelity=node_cfg.gate_fidelity,
                        mem_fidelities=mem_fidelities,
                    )
                else:
                    qdevice = build_nv_qdevice(
                        name=f"{node_cfg.name}_NVQDevice", cfg=self._nv_config
                    )
            elif hardware == QuantumHardware.TrappedIon:
                raise ValueError("TrappedIon hardware not supported.")
            else:  # use generic hardware (vanilla flavour)
                qdevice = QDevice(
                    name=f"{node_cfg.name}_QDevice",
                    num_qubits=len(node_cfg.qubits),
                    gate_fidelity=node_cfg.gate_fidelity,
                    mem_fidelities=mem_fidelities,
                )
            node = Node(name=node_cfg.name, ID=i, qmemory=qdevice)
            self.add_node(node)

    def _create_link_layer_services(self) -> None:
        """
        Create a MagicNetworkLayerProtocol for each link in the network,
        and create link layer services for each of the endpoints for each link.
        """

        for node_name in self.nodes:
            self._link_layer_services[node_name] = {}

        for link in self._network_config.links:
            node1 = self.get_node(link.node_name1)
            node2 = self.get_node(link.node_name2)
            node_pair = (node1, node2)
            magic_dist = self._create_link_distributor(link)

            magic_protocol = MagicNetworkLayerProtocol(
                nodes=node_pair,
                magic_distributor=magic_dist,
                translation_unit=SingleClickTranslationUnit(),
                path=[link.name],
                network=self,
            )

            for node, remote_node in [node_pair, reversed(node_pair)]:
                link_layer_service = LinkLayerService(
                    node=node,
                    magic=True,
                    magic_protocol=magic_protocol,
                    reaction_handler=None,
                )
                self._link_layer_services[node.name][
                    remote_node.ID
                ] = link_layer_service

    def _create_link_distributor(
        self, link: Link, state_delay: Optional[float] = 1000
    ) -> MagicDistributor:
        """
        Create a MagicDistributor for a pair of nodes,
        based on configuration in a `Link` object.
        """
        node1 = self.get_node(link.node_name1)
        node2 = self.get_node(link.node_name2)

        try:
            noise_type = NoiseType(link.noise_type)
            if noise_type == NoiseType.NoNoise:
                model_params = PerfectModelParameters(state_delay=state_delay)
                return PerfectStateMagicDistributor(
                    nodes=[node1, node2], model_params=model_params
                )
            elif (
                noise_type == NoiseType.Depolarise
            ):  # use Depolarise distributor defined in this module
                noise = 1 - link.fidelity
                return LinearDepolariseMagicDistributor(
                    nodes=[node1, node2], depolar_noise=noise, state_delay=state_delay
                )
            elif (
                noise_type == NoiseType.DiscreteDepolarise
            ):  # use Depolarise distributor defined in netsquid_magic
                noise = 1 - link.fidelity
                model_params = DepolariseModelParameters(prob_max_mixed=noise)
                return DepolariseMagicDistributor(
                    nodes=[node1, node2],
                    model_params=model_params,
                    state_delay=state_delay,
                )
            elif noise_type == NoiseType.Bitflip:
                flip_prob = 1 - link.fidelity
                model_params = BitFlipModelParameters(flip_prob=flip_prob)
                return BitflipMagicDistributor(
                    model_params=model_params,
                    state_delay=state_delay,
                    nodes=[node1, node2],
                )
        except ValueError:
            raise TypeError(f"Noise type {link.noise_type} not valid")


class MagicNetworkLayerProtocol(MagicLinkLayerProtocol):
    """
    Same as a MagicLinkLayerProtocol, but contains information about a path in the network.
    This path is not actually used by the magic protocol.
    Furthermore, it logs requests and deliveries to the NetworkLogger of the network.
    """

    def __init__(
        self,
        nodes: Tuple[Node, Node],
        magic_distributor: MagicDistributor,
        translation_unit: TranslationUnit,
        path: List[str],
        network: NetSquidNetwork,
    ) -> None:
        super().__init__(
            nodes=nodes,
            magic_distributor=magic_distributor,
            translation_unit=translation_unit,
        )

        self.path: List[str] = path
        self.network: NetSquidNetwork = network

    def _get_unused_memory_positions(self) -> Optional[Dict[int, int]]:
        # NOTE override this method in order to be able to see what qubits are being used
        # In the current version of the magic link layer protocol, if there are memory_positions
        # then the generation of the pair will for sure start. However this could
        # break in future versions (without being clear that this is a breaking change for us)
        memory_positions = super()._get_unused_memory_positions()
        if memory_positions is None:
            return None

        nodes, qubit_ids, qubit_states = self._get_log_data(
            memory_positions=memory_positions,
            get_qubit_states=False,
        )

        nodes = [node.name for node in self.nodes]
        qubit_ids = [memory_positions[node.ID] for node in self.nodes]

        if get_running_backend(block=False) is None:
            # TODO: handle in a better way
            qubit_groups = None
        else:
            qubit_groups = QubitInfo.get_qubit_groups()

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_type=None,  # unknown at this point
            ent_stage=EntanglementStage.START,
            meas_bases=None,
            meas_outcomes=None,
            nodes=nodes,
            path=list(self.path),
            qubit_ids=qubit_ids,
            qubit_groups=qubit_groups,
            msg=f"start entanglement creation between {nodes[0]} and {nodes[1]}",
        )

        logger.debug(f"scheduling entanglement at positions {memory_positions}")
        return memory_positions  # type: ignore

    def _get_log_data(
        self, memory_positions: Dict[int, int], get_qubit_states: bool = False
    ) -> Tuple[List[str], List[int], List[Optional[T_SingleQubitState]]]:
        nodes = []
        qubit_ids = []
        qubit_states = []
        for node in self.nodes:
            nodes.append(node.name)
            qubit_id = memory_positions[node.ID]
            qubit_ids.append(qubit_id)
            if get_qubit_states:
                qubit_states.append(self._get_qubit_state(node, qubit_id))
            else:
                qubit_states.append(None)
        return nodes, qubit_ids, qubit_states

    @staticmethod
    def _get_qubit_state(node: Node, phys_pos: int) -> Optional[T_SingleQubitState]:
        try:
            qubit = node.qmemory._get_qubits(phys_pos)[0]
        except MemPositionBusyError:
            with node.qmemory._access_busy_memory([phys_pos]):
                logger.info("NOTE Accessing qubit from busy memory")
                qubit = node.qmemory._get_qubits(phys_pos, skip_noise=True)[0]
        if qubit is None:
            qubit_state = None
        else:
            qubit_state = qapi.reduced_dm(qubit).tolist()
        return qubit_state

    def _handle_label_delivery(self, event):
        """
        Handles the completion of an entanglement generation
        Updates, the requests, number of pairs left etc,
        measures the qubits in case of type M and returns the corresponding OK message
        """

        # NOTE: This is a literal copy of the _handle_delivery method in the
        # netsquid_magic package, with one change: the `messages` dict is
        # returned at the end, so that their contents can be logged.
        try:
            queue_item = self._pop_from_requests_in_process(event)
        except KeyError:
            # This indicates that this delivery event is not the "reference" delivery event returned by add_delivery
            # of the magic distributor. Since the below operations only need to be executed once, we can skip this.
            return

        if queue_item is None:
            return

        request = queue_item.request
        node_id = queue_item.node_id
        create_id = queue_item.create_id
        memory_positions = self._magic_distributor.peek_delivery(event).memory_positions

        logger.debug(
            f"Handling delivery of entanglement at positions {memory_positions}"
        )

        # Decrement remaining pairs
        self._decrement_pairs_left(node_id=node_id, create_id=create_id)

        # Get Bell state from outcome
        midpoint_outcome = self._magic_distributor.get_label(event)
        bell_state = self._get_bell_state(midpoint_outcome=midpoint_outcome)

        # Create response messages and measure qubits if type M or R
        sequence_number = self._get_next_sequence_number()
        messages = {}
        for node in self.nodes:
            if node.ID != request.remote_node_id:
                directionality_flag = 0
            else:
                directionality_flag = 1

            # Get the ID of the other node
            for remote_node in self.nodes:
                if remote_node.ID != node.ID:
                    remote_node_id = remote_node.ID
                    break
            else:
                raise RuntimeError("Could not get the remote node ID")

            memory_position = memory_positions[node.ID][0]
            if isinstance(request, ReqCreateAndKeep):
                msg = ResCreateAndKeep(
                    create_id=create_id,
                    logical_qubit_id=memory_position,
                    directionality_flag=directionality_flag,
                    sequence_number=sequence_number,
                    purpose_id=request.purpose_id,
                    remote_node_id=remote_node_id,
                    goodness=request.minimum_fidelity,
                    time_of_goodness=sim_time(),
                    bell_state=bell_state,
                )
            elif isinstance(request, ReqMeasureDirectly):
                measurement_outcome, measurement_basis = self._measure_qubit(
                    node, request, memory_position
                )
                msg = ResMeasureDirectly(
                    create_id=create_id,
                    measurement_outcome=measurement_outcome,
                    measurement_basis=measurement_basis,
                    directionality_flag=directionality_flag,
                    sequence_number=sequence_number,
                    purpose_id=request.purpose_id,
                    remote_node_id=remote_node_id,
                    goodness=request.minimum_fidelity,
                    bell_state=bell_state,
                )
            else:
                raise NotADirectoryError(
                    "Requests of type other than K or M is not yet supported"
                )
            messages[node.ID] = msg

        # Respond to the user
        # NOTE: we do this *before* calling self._handle_next() which might be problematic (?).
        for node in self.nodes:
            self.react_to(node.ID, messages[node.ID])

        # For Measure Directly requests, check the response messages
        # to be able to log the bases and outcomes.
        meas_bases: Optional[List[int]]
        meas_outcomes: Optional[List[int]]
        if isinstance(request, ReqMeasureDirectly):
            meas_bases = [resp.measurement_basis.value for resp in messages.values()]
            meas_outcomes = [resp.measurement_outcome for resp in messages.values()]
        else:
            meas_bases = None
            meas_outcomes = None

        memory_positions = {
            node_id: mem_pos[0] for node_id, mem_pos in memory_positions.items()
        }

        node_names = [node.name for node in self.nodes]
        qubit_ids = [memory_positions[node.ID] for node in self.nodes]

        for node in self.nodes:
            QubitInfo.update_qubits_used(node.name, memory_positions[node.ID], True)

        if get_running_backend(block=False) is None:
            # TODO: handle in a better way
            qubit_groups = None
        else:
            qubit_groups = QubitInfo.get_qubit_groups()

        # qlink-layer 0.1.0 type
        if isinstance(request, ReqCreateAndKeep):
            qlink_0_1_type = RequestType.K
        elif isinstance(request, ReqMeasureDirectly):
            qlink_0_1_type = RequestType.M
        else:
            raise ValueError(f"Unsupported type of request {request}")

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_type=qlink_0_1_type,
            ent_stage=EntanglementStage.FINISH,
            meas_bases=meas_bases,
            meas_outcomes=meas_outcomes,
            nodes=node_names,
            path=list(self.path),
            qubit_ids=qubit_ids,
            qubit_groups=qubit_groups,
            msg=f"entanglement of type {qlink_0_1_type.value} created between {node_names[0]} and {node_names[1]}",
        )

        self._schedule_now(EprDeliveredEvent)

        self._handle_next()


class QDevice(QuantumProcessor):
    # Default instructions. Durations are arbitrary
    _default_phys_instructions: List[PhysicalInstruction] = [
        PhysicalInstruction(ns_instructions.INSTR_INIT, duration=1e5),
        PhysicalInstruction(ns_instructions.INSTR_X, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_Y, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_Z, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_H, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_K, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_S, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_T, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_ROT_X, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_ROT_Y, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_ROT_Z, duration=1e3),
        PhysicalInstruction(ns_instructions.INSTR_CNOT, duration=5e5),
        PhysicalInstruction(ns_instructions.INSTR_CZ, duration=5e5),
    ]

    def __init__(
        self,
        name: str = "QDevice",
        num_qubits: int = 5,
        phys_instrs: Optional[List[PhysicalInstruction]] = None,
        gate_fidelity: float = 1.0,
        mem_fidelities: Optional[List[float]] = None,
    ) -> None:
        self.gate_fidelity = gate_fidelity
        if mem_fidelities is None:
            mem_fidelities = [T1T2NoiseModel(0, 0) for _ in range(num_qubits)]
        if phys_instrs is None:
            phys_instrs = copy.deepcopy(QDevice._default_phys_instructions)
        for instr in phys_instrs:
            instr.quantum_noise_model = DepolarNoiseModel(
                depolar_rate=(1 - gate_fidelity), time_independent=True
            )

        super().__init__(
            name=name,
            num_positions=num_qubits,
            phys_instructions=phys_instrs,
            memory_noise_models=mem_fidelities,
        )


class NVQDevice(QDevice):
    """
    A QDevice with NV hardware.
    """

    def __init__(
        self,
        name: str = "NVQDevice",
        num_qubits: int = 5,
        gate_fidelity: float = 1,
        mem_fidelities: Optional[List[float]] = None,
    ) -> None:
        phys_instrs: List[PhysicalInstruction] = [
            PhysicalInstruction(ns_instructions.INSTR_INIT, duration=1),
            PhysicalInstruction(ns_instructions.INSTR_ROT_X, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_ROT_Y, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_ROT_Z, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_CXDIR, duration=5),
            PhysicalInstruction(ns_instructions.INSTR_CYDIR, duration=5),
        ]

        super().__init__(
            name=name,
            num_qubits=num_qubits,
            phys_instrs=phys_instrs,
            gate_fidelity=gate_fidelity,
            mem_fidelities=mem_fidelities,
        )


class LinearDepolariseMagicDistributor(MagicDistributor):
    """
    Distributes (noisy) EPR pairs to 2 connected nodes, using samplers created
    by a :class:`LinearDepolariseStateSamplerFactory`.
    """

    def __init__(self, nodes, depolar_noise, **kwargs):
        """
        Parameters
        ----------
        nodes : list of :obj:`~netsquid.nodes.node.Node`
            Pair of nodes to which noisy EPR pairs will be distributed.
        depolar_noise : float
            Depolarizing noise.
        """
        self.depolar_noise = depolar_noise
        super().__init__(
            delivery_sampler_factory=LinearDepolariseStateSamplerFactory(),
            nodes=nodes,
            **kwargs,
        )

    def add_delivery(self, memory_positions, **kwargs):
        return super().add_delivery(
            memory_positions=memory_positions,
            depolar_noise=self.depolar_noise,
            **kwargs,
        )


class LinearDepolariseStateSamplerFactory(HeraldedStateDeliverySamplerFactory):
    """
    A factory for samplers that produce a linear combination of a perfect EPR pair and the maximally
    mixed state over the two 2 nodes (I/4).
    """

    def __init__(self):
        super().__init__(
            func_delivery=self._delivery_func,
        )

    @staticmethod
    def _delivery_func(depolar_noise, **kwargs):
        """
        Parameters
        ----------
        depolar_noise : float
            Used to calculate the linear combination of the original state
            and the maximally mixed state.

        Returns
        -------
        tuple `(state_sampler, probabilities)`
        """
        epr_state = np.array(
            [[0.5, 0, 0, 0.5], [0, 0, 0, 0], [0, 0, 0, 0], [0.5, 0, 0, 0.5]],
            dtype=np.complex,
        )
        maximally_mixed = np.array(
            [[0.25, 0, 0, 0], [0, 0.25, 0, 0], [0, 0, 0.25, 0], [0, 0, 0, 0.25]],
            dtype=np.complex,
        )
        return (
            StateSampler(
                qreprs=[
                    (1 - depolar_noise) * epr_state + depolar_noise * maximally_mixed
                ],
                probabilities=[1],
            ),
            1,
        )

    @staticmethod
    def _get_success_probability(**kwargs):
        return 1
