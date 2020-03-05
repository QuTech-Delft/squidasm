
from netsquid.nodes import Node
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components.instructions import INSTR_INIT, INSTR_X, INSTR_H, INSTR_CNOT


def get_node(name, num_qubits=5):
    qdevice = get_qdevice(name=f"{name}_QPD", num_qubits=num_qubits)
    node = Node(name, qmemory=qdevice)

    return node


def get_nodes(names, num_qubits=5):
    nodes = {}
    for name in names:
        nodes[name] = get_node(name=name, num_qubits=num_qubits)

    return nodes


def get_qdevice(name="QPD", num_qubits=5):
    return QuantumProcessor(name=name, num_positions=num_qubits, phys_instructions=[
        # TODO durations
        PhysicalInstruction(INSTR_INIT, duration=1),
        PhysicalInstruction(INSTR_X, duration=2),
        PhysicalInstruction(INSTR_H, duration=3),
        PhysicalInstruction(INSTR_CNOT, duration=3),
    ])
