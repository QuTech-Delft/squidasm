from netsquid.nodes import Node
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components import instructions as ns_instructions

from netsquid_netconf.builder import ComponentBuilder
from netsquid_netconf.netconf import netconf_generator, Loader, _nested_dict_set
from netsquid.components import QuantumProcessor, PhysicalInstruction, Instruction
from netsquid.components.models.qerrormodels import T1T2NoiseModel


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


class DemoQDevice(QuantumProcessor):
    def __init__(self, name="DemoQDevice", num_qubits=5, gate_fidelity=1, T1=0, T2=0):
        self.gate_fidelity = gate_fidelity
        self.T1 = T1
        self.T2 = T2
        phys_instrs = default_phys_instructions
        for instr in phys_instrs:
            instr.q_noise_model = T1T2NoiseModel(T1, T2)
        super().__init__(name=name, num_positions=num_qubits, phys_instructions=phys_instrs, memory_noise_models=T1T2NoiseModel(T1, T2))


# def get_node(name, node_id=None, num_qubits=5, network_config=None):
#     qdevice = get_qdevice(name=f"{name}_QPD", num_qubits=num_qubits, network_config=network_config)
#     node = Node(name, ID=node_id, qmemory=qdevice)

#     return node


def get_nodes(names, node_ids=None, num_qubits=5, network_config=None):
    if node_ids is None:
        node_ids = list(range(len(names)))
    assert len(names) == len(node_ids), "Wrong number of node IDs"
    nodes = {}

    print(f"get_nodes: {network_config}")
    for name, value in network_config['components'].items():
        if isinstance (value, Node):
            print(f"found node with name: {name}")
            if name in names:
                nodes[name] = value
            
    # print(f"nodes: {nodes}")

    node = nodes['alice']
    # print(f"alice: qmem: {node.qmemory}")
    # print(f"alice: qmem.num_positions: {node.qmemory.num_positions}")
    # print(f"qmem.phys_instructions: {node.qmemory.get_physical_instructions()}")
    phys_instrs = node.qmemory.get_physical_instructions()
    # for instr in phys_instrs:
    #     print(f"alice: qmem.q_noise_model: {instr.q_noise_model}")

    node = nodes['bob']
    # print(f"bob: qmem: {node.qmemory}")
    # print(f"bob: qmem.num_positions: {node.qmemory.num_positions}")
    # print(f"qmem.phys_instructions: {node.qmemory.get_physical_instructions()}")
    phys_instrs = node.qmemory.get_physical_instructions()
    # for instr in phys_instrs:
    #     print(f"bob: qmem.q_noise_model: {instr.q_noise_model}")

    # for name, node_id in zip(names, node_ids):
    #     nodes[name] = get_node(
    #         name=name,
    #         node_id=node_id,
    #         num_qubits=num_qubits,
    #         network_config=network_config,
    #     )

    return nodes
