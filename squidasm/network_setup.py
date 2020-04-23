from netsquid.nodes import Node
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components import instructions as ns_instructions


def get_node(name, node_id=None, num_qubits=5, network_config=None):
    qdevice = get_qdevice(name=f"{name}_QPD", num_qubits=num_qubits, network_config=network_config)
    node = Node(name, ID=node_id, qmemory=qdevice)

    return node


def get_nodes(names, node_ids=None, num_qubits=5, network_config=None):
    if node_ids is None:
        node_ids = list(range(len(names)))
    assert len(names) == len(node_ids), "Wrong number of node IDs"
    nodes = {}
    for name, node_id in zip(names, node_ids):
        nodes[name] = get_node(
            name=name,
            node_id=node_id,
            num_qubits=num_qubits,
            network_config=network_config,
        )

    return nodes


def get_qdevice(name="QPD", num_qubits=5, network_config=None):
    if network_config is None:
        phys_instructions = [
            # TODO durations (currently arbitary)
            PhysicalInstruction(ns_instructions.INSTR_INIT, duration=1),
            PhysicalInstruction(ns_instructions.INSTR_X, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_Y, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_Z, duration=2),
            PhysicalInstruction(ns_instructions.INSTR_H, duration=3),
            PhysicalInstruction(ns_instructions.INSTR_K, duration=3),
            PhysicalInstruction(ns_instructions.INSTR_S, duration=3),
            PhysicalInstruction(ns_instructions.INSTR_T, duration=4),
            PhysicalInstruction(ns_instructions.INSTR_CNOT, duration=5),
            PhysicalInstruction(ns_instructions.INSTR_CZ, duration=5),
        ]
    else:
        # TODO this is temporary, config file will change
        gates = network_config.get('gates')
        if gates is None:
            phys_instructions = None
        else:
            phys_instructions = []
            for gate in gates:
                instruction = getattr(ns_instructions, gate['instruction'])
                duration = gate['duration']
                phys_instructions.append(PhysicalInstruction(instruction=instruction, duration=duration))

    return QuantumProcessor(name=name, num_positions=num_qubits, phys_instructions=phys_instructions)
