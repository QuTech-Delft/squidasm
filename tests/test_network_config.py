from netqasm.yaml_util import load_yaml
from squidasm.network.config import Qubit, Node, Link


def test():
    cfg = load_yaml("network_config.yaml")
    try:
        node_cfgs = cfg['nodes']
        link_cfgs = cfg['links']

        nodes = []
        for node_cfg in node_cfgs:
            qubit_cfgs = node_cfg['qubits']
            qubits = []
            for qubit_cfg in qubit_cfgs:
                qubit = Qubit(
                    id=qubit_cfg['id'],
                    t1=qubit_cfg['t1'],
                    t2=qubit_cfg['t2'],
                )
                qubits += [qubit]

            node = Node(
                name=node_cfg['name'],
                qubits=qubits,
                gate_fidelity=node_cfg['gate_fidelity']
            )
            nodes += [node]

        links = []
        for link_cfg in link_cfgs:
            link = Link(
                name=link_cfg['name'],
                node_name1=link_cfg['node_name1'],
                node_name2=link_cfg['node_name2'],
                noise_type=link_cfg['noise_type'],
                fidelity=link_cfg['fidelity']
            )
            links += [link]
    except KeyError:
        raise ValueError("Invalid network configuration")

    print(nodes)
    print(links)


if __name__ == "__main__":
    test()
