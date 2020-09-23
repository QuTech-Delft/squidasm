import os
from typing import List, Dict, Optional

import netsquid as ns
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components import instructions as ns_instructions
from netsquid.components.models.qerrormodels import T1T2NoiseModel, DepolarNoiseModel
from netsquid.nodes import Network, Node

from netsquid_magic.link_layer import (
    LinkLayerService,
    MagicLinkLayerProtocol,
    SingleClickTranslationUnit,
)

from netsquid_magic.magic_distributor import (
    MagicDistributor,
    PerfectStateMagicDistributor,
    DepolariseMagicDistributor,
    BitflipMagicDistributor
)

from squidasm.network.config import NetworkConfig, NoiseType, QuantumHardware
from squidasm.network.config import Link

from netqasm.output import EntanglementStage
from squidasm.output import InstrLogger

from netqasm.logging import get_netqasm_logger
from netqasm.output import NetworkLogger

logger = get_netqasm_logger()


class NetSquidNetwork(Network):
    """
    Represents the collection of nodes and links in the simulated network.

    The constructor creates Nodes based on the given NetworkConfig,
    and creates link layer services for each pair of connected nodes.
    """

    def __init__(self, network_config: NetworkConfig, global_log_dir=None):
        if global_log_dir is not None:
            logger_path = os.path.join(global_log_dir, "network_log.yaml")
            self._global_logger = NetworkLogger(logger_path)
        else:
            self._global_logger = None

        self._network_config = network_config
        self._node_hardware_types: Dict[str, QuantumHardware] = {}

        # create NetSquid `Node`s and add them to this `Network`
        self._build_network()

        self._link_layer_services: Dict[str, Dict[int, LinkLayerService]] = dict()
        self._create_link_layer_services()

    @property
    def node_hardware_types(self):
        return self._node_hardware_types

    @property
    def link_layer_services(self):
        return self._link_layer_services

    def global_log(self, *args, **kwargs):
        if self._global_logger is not None:
            self._global_logger.log(*args, **kwargs)

    def _build_network(self):
        for i, node_cfg in enumerate(self._network_config.nodes):
            try:
                hardware = QuantumHardware(node_cfg.hardware)
            except Exception:
                logger.warn("Hardware type not valid. Using a generic one.")
                hardware = QuantumHardware.Generic
            self._node_hardware_types[node_cfg.name] = hardware

            mem_fidelities = [T1T2NoiseModel(q.t1, q.t2) for q in node_cfg.qubits]

            if hardware == QuantumHardware.NV:
                qdevice = NVQDevice(
                    name=f"{node_cfg.name}_NVQDevice",
                    num_qubits=len(node_cfg.qubits),
                    gate_fidelity=node_cfg.gate_fidelity,
                    mem_fidelities=mem_fidelities,
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
            node = Node(
                name=node_cfg.name,
                ID=i,
                qmemory=qdevice
            )
            self.add_node(node)

    def _create_link_layer_services(self):
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
                path=None,
                network=self,
            )

            for node, remote_node in [node_pair, reversed(node_pair)]:
                link_layer_service = LinkLayerService(
                    node=node,
                    magic=True,
                    magic_protocol=magic_protocol,
                    reaction_handler=None,
                )
                self._link_layer_services[node.name][remote_node.ID] = link_layer_service

    def _create_link_distributor(self, link: Link, state_delay: Optional[float] = 1.) -> MagicDistributor:
        """
        Create a MagicDistributor for a pair of nodes,
        based on configuration in a `Link` object.
        """
        node1 = self.get_node(link.node_name1)
        node2 = self.get_node(link.node_name2)

        try:
            noise_type = NoiseType(link.noise_type)
            if noise_type == NoiseType.NoNoise:
                return PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=state_delay)
            elif noise_type == NoiseType.Depolarise:
                noise = 1 - link.fidelity
                return DepolariseMagicDistributor(nodes=[node1, node2], prob_max_mixed=noise, state_delay=state_delay)
            elif noise_type == NoiseType.Bitflip:
                flip_prob = 1 - link.fidelity
                return BitflipMagicDistributor(nodes=[node1, node2], flip_prob=flip_prob, state_delay=state_delay)
        except ValueError:
            raise TypeError(f"Noise type {link.noise_type} not valid")


class MagicNetworkLayerProtocol(MagicLinkLayerProtocol):
    """
    Same as a MagicLinkLayerProtocol, but contains information about a path in the network.
    This path is not actually used by the magic protocol.
    Furthermore, it logs requests and deliveries to the NetworkLogger of the network.
    """
    def __init__(self, nodes, magic_distributor, translation_unit, path: List[str], network):
        super().__init__(
            nodes=nodes, magic_distributor=magic_distributor, translation_unit=translation_unit)

        self.path = path
        self.network = network

    def _handle_create_request(self, node_id, request):
        node0 = self.nodes[0].name
        node1 = self.nodes[1].name
        qubit_groups = InstrLogger._get_qubit_groups()

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_stage=EntanglementStage.START,
            nodes=[node0, node1],
            qubit_ids=[None, None],
            qubit_states=[None, None],
            qubit_groups=qubit_groups,
            msg=f"start entanglement creation between {node0} and {node1}",
        )

        return super()._handle_create_request(node_id=node_id, request=request)

    def _handle_delivery(self, event):
        delivery = self._magic_distributor.peek_delivery(event)
        memory_positions = delivery.memory_positions

        super()._handle_delivery(event)

        node0 = self.nodes[0].name
        node1 = self.nodes[1].name
        node0_pos, node1_pos = memory_positions.values()
        qubit0 = node0_pos[0]
        qubit1 = node1_pos[0]
        qubit_groups = InstrLogger._get_qubit_groups()

        self.network.global_log(
            sim_time=ns.sim_time(),
            ent_stage=EntanglementStage.FINISH,
            nodes=[node0, node1],
            qubit_ids=[qubit0, qubit1],
            qubit_states=[None, None],
            qubit_groups=qubit_groups,
            msg=f"entanglement created between {node0} and {node1}",
        )


class QDevice(QuantumProcessor):
    # Default instructions. Durations are arbitrary
    _default_phys_instructions = [
        PhysicalInstruction(ns_instructions.INSTR_INIT, duration=1),
        PhysicalInstruction(ns_instructions.INSTR_X, duration=2),
        PhysicalInstruction(ns_instructions.INSTR_Y, duration=2),
        PhysicalInstruction(ns_instructions.INSTR_Z, duration=2),
        PhysicalInstruction(ns_instructions.INSTR_H, duration=3),
        PhysicalInstruction(ns_instructions.INSTR_K, duration=3),
        PhysicalInstruction(ns_instructions.INSTR_S, duration=3),
        PhysicalInstruction(ns_instructions.INSTR_T, duration=4),
        PhysicalInstruction(ns_instructions.INSTR_ROT_X, duration=4),
        PhysicalInstruction(ns_instructions.INSTR_ROT_Y, duration=4),
        PhysicalInstruction(ns_instructions.INSTR_ROT_Z, duration=4),
        PhysicalInstruction(ns_instructions.INSTR_CNOT, duration=5),
        PhysicalInstruction(ns_instructions.INSTR_CZ, duration=5),
    ]

    def __init__(
        self,
        name="QDevice",
        num_qubits=5,
        phys_instrs=None,
        gate_fidelity=1,
        mem_fidelities=None,
    ):
        self.gate_fidelity = gate_fidelity
        if mem_fidelities is None:
            mem_fidelities = [T1T2NoiseModel(0, 0) for _ in range(num_qubits)]
        if phys_instrs is None:
            phys_instrs = QDevice._default_phys_instructions
        for instr in phys_instrs:
            instr.q_noise_model = DepolarNoiseModel(depolar_rate=(1-gate_fidelity))

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
    def __init__(self, name="NVQDevice", num_qubits=5, gate_fidelity=1, mem_fidelities=None):
        phys_instrs = [
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
