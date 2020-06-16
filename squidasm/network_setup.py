from typing import List

from netsquid.nodes import Node
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components import instructions as ns_instructions

from netsquid_netconf.builder import ComponentBuilder
from netsquid_netconf.netconf import netconf_generator, Loader, _nested_dict_set
from netsquid.components import QuantumProcessor, PhysicalInstruction, Instruction
from netsquid.components.models.qerrormodels import T1T2NoiseModel
from netsquid.nodes import Node, Connection, Network
from netsquid_magic.magic_distributor import MagicDistributor
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor
from netsquid_magic.state_delivery_sampler import HeraldedStateDeliverySamplerFactory

from squidasm.network_config import NodeLink, NoiseType, DepolariseMagicDistributor, BitflipMagicDistributor


class BackendNetwork(Network):
    def __init__(self, node_names, network_config=None):
        super().__init__(name="BackendNetwork")
        self.links: List[MagicDistributor] = []

        if network_config is not None:
            self.init_from_config(network_config)
        else:
            self.init_default(node_names)

    def init_default(self, node_names):
        for node_name in node_names:
            node = Node(name=node_name, qmemory=QDevice())
            self.add_node(node)
            
        for node_name1 in self.nodes:
            for node_name2 in self.nodes:
                if node_name1 == node_name2:
                    continue
                node_link = NodeLink(name="", node_name1=node_name1, node_name2=node_name2)
                link = self.get_link_distributor(node_link)
                self.links.append(link)

        pass

    def init_from_config(self, network_config):
        components = network_config["components"]
        for comp in components.values():
            if isinstance(comp, Node):
                self.add_node(comp)
            elif isinstance(comp, NodeLink):
                link = self.get_link_distributor(comp)
                self.links.append(link)


    def get_link_distributor(self, link: NodeLink):
        node1 = self.get_node(link.node_name1)
        node2 = self.get_node(link.node_name2)

        if link.noise_type == NoiseType.NoNoise:
            return PerfectStateMagicDistributor(nodes=[node1, node2])
        elif link.noise_type == NoiseType.Depolarise:
            noise = 1 - link.fidelity
            return DepolariseMagicDistributor(nodes=[node1, node2], noise=noise)
        elif link.noise_type == NoiseType.BitFlip:
            flip_prob = 1 - link.fidelity
            return BitflipMagicDistributor(nodes=[node1, node2], flip_prob=flip_prob)
        else:
            raise TypeError(f"Noise type {link.noise_type} not valid")


default_phys_instructions = [
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


class QDevice(QuantumProcessor):
    def __init__(self, name="QDevice", num_qubits=5, gate_fidelity=1, T1=0, T2=0):
        self.gate_fidelity = gate_fidelity
        self.T1 = T1
        self.T2 = T2
        phys_instrs = default_phys_instructions
        for instr in phys_instrs:
            instr.q_noise_model = T1T2NoiseModel(T1, T2)
        super().__init__(name=name, num_positions=num_qubits, phys_instructions=phys_instrs, memory_noise_models=T1T2NoiseModel(T1, T2))
