import os
from typing import List, Dict

from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components import instructions as ns_instructions
from netsquid.components.models.qerrormodels import T1T2NoiseModel
from netsquid.nodes import Network, Node
from netsquid_magic.magic_distributor import (
    MagicDistributor,
    PerfectStateMagicDistributor,
    DepolariseMagicDistributor,
    BitflipMagicDistributor
)

from .config import NodeLinkConfig, NoiseType

from netqasm.logging import get_netqasm_logger
from netqasm.output import NetworkLogger
logger = get_netqasm_logger()


class BackendNetwork(Network):
    """
    Represents the collection of nodes and links in the simulated network.
    Apart from the `Nodes`s, it maintains a list of `MagicDistributor`s called "links",
    which represent a entanglement-creating connection between 2 nodes.
    """

    def __init__(self, node_names, global_log_dir=None, network_config=None):
        """
        BackendNetwork constructor.
        `network_config` should be a config object generated from `network.yaml`.
        If None, a default network is constructed based on the names in `node_names`,
        where each pair of nodes is connected with a perfect EPR distributor.
        """
        super().__init__(name="BackendNetwork")
        self.links: List[MagicDistributor] = []

        if global_log_dir is not None:
            logger_path = os.path.join(global_log_dir, "network_log.yaml")
            self._global_logger = NetworkLogger(logger_path)
        else:
            self._global_logger = None

        # paths for creating entanglement between nodes
        self.paths: Dict[str, Dict[str, List[str]]] = {}

        if network_config is not None:
            self._init_from_config(network_config)
        else:
            self._init_default(node_names)

    def global_log(self, *args, **kwargs):
        if self._global_logger is not None:
            self._global_logger.log(*args, **kwargs)

    def _init_default(self, node_names):
        for i, node_name in enumerate(node_names):
            node = Node(name=node_name, ID=i, qmemory=QDevice())
            self.add_node(node)

        for node_name1 in self.nodes:
            for node_name2 in self.nodes:
                if node_name1 == node_name2:
                    continue
                link_config = NodeLinkConfig(name="", node_name1=node_name1, node_name2=node_name2)
                link = self.get_link_distributor(link_config)
                self.links.append(link)

                # path is same as link
                self.paths[(node_name1, node_name2)] = [node_name1, node_name2]

        pass

    def _init_from_config(self, network_config):
        components = network_config["components"]
        for comp in components.values():
            if isinstance(comp, Node):
                # TODO: Make this nicer
                # For now it's a quick fix to work with netsquid 0.9.8 (addition of ComponentHierarchyError)
                super_comp = comp.supercomponent
                super_comp.rem_subcomponent(comp.name)
                self.add_node(comp)
            elif isinstance(comp, NodeLinkConfig):
                link = self.get_link_distributor(comp)
                self.links.append(link)

        for node_name1 in self.nodes:
            for node_name2 in self.nodes:
                if node_name1 == node_name2:
                    continue

                # For now: path is same as link
                # TODO: get path from network config file, or compute it based on simple routing protocol
                self.paths[(node_name1, node_name2)] = [node_name1, node_name2]

    def get_link_distributor(self, link: NodeLinkConfig) -> MagicDistributor:
        """
        Create a MagicDistributor for a pair of nodes,
        based on configuration in a `NodeLinkConfig` object.
        """
        node1 = self.get_node(link.node_name1)
        node2 = self.get_node(link.node_name2)

        if link.noise_type == NoiseType.NoNoise:
            return PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=1e-5)
        elif link.noise_type == NoiseType.Depolarise:
            noise = 1 - link.fidelity
            return DepolariseMagicDistributor(nodes=[node1, node2], prob_max_mixed=noise, state_delay=1e-5)
        elif link.noise_type == NoiseType.Bitflip:
            flip_prob = 1 - link.fidelity
            return BitflipMagicDistributor(nodes=[node1, node2], flip_prob=flip_prob, state_delay=1e-5)
        else:
            raise TypeError(f"Noise type {link.noise_type} not valid")


class QDevice(QuantumProcessor):
    """
    A wrapper around a NetSquid `QuantumProcessor`, allowing specification
    of gate fidelity (applying to all gates), and T1 and T2 values (applying to all qubits).
    """

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
        # TODO: move to separate NV QDevice class
        PhysicalInstruction(ns_instructions.INSTR_CROT_X, duration=5),
    ]

    def __init__(self, name="QDevice", num_qubits=5, gate_fidelity=1, T1=0, T2=0):
        self.gate_fidelity = gate_fidelity
        self.T1 = T1
        self.T2 = T2
        phys_instrs = QDevice._default_phys_instructions
        for instr in phys_instrs:
            instr.q_noise_model = T1T2NoiseModel(T1, T2)

        super().__init__(
            name=name,
            num_positions=num_qubits,
            phys_instructions=phys_instrs,
            memory_noise_models=T1T2NoiseModel(T1, T2))
