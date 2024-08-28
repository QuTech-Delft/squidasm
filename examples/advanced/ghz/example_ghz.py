from typing import List

from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.qlinks.perfect import PerfectQLinkConfig

from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util.routines import create_ghz
from squidasm.util.util import create_complete_graph_network


class GHZProgram(Program):
    def __init__(self, name: str, node_names: List[str]):
        self.name = name
        self.node_names = node_names
        self.peer_names = [peer for peer in self.node_names if peer != self.name]

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=self.peer_names,
            epr_sockets=self.peer_names,
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        connection = context.connection

        # Find the index of current node
        i = self.node_names.index(self.name)
        down_epr_socket = None
        up_epr_socket = None
        down_socket = None
        up_socket = None

        if i > 0:
            # i == 0 is the start node and has no node "down"
            down_name = self.node_names[i - 1]
            down_epr_socket = context.epr_sockets[down_name]
            down_socket = context.csockets[down_name]
        if i < len(self.node_names) - 1:
            # Last node is the end node and has no node "up"
            up_name = self.node_names[i + 1]
            up_epr_socket = context.epr_sockets[up_name]
            up_socket = context.csockets[up_name]

        # noinspection PyTupleAssignmentBalance
        qubit, m = yield from create_ghz(
            connection,
            down_epr_socket,
            up_epr_socket,
            down_socket,
            up_socket,
            do_corrections=True,
        )

        q_measure = qubit.measure()
        yield from connection.flush()

        return {"name": self.name, "result": int(q_measure)}


if __name__ == "__main__":
    num_nodes = 6
    node_names_ = [f"Node_{i}" for i in range(num_nodes)]

    cfg = create_complete_graph_network(
        node_names_,
        "perfect",
        PerfectQLinkConfig(state_delay=100),
        clink_typ="default",
        clink_cfg=DefaultCLinkConfig(delay=100),
    )

    programs = {name: GHZProgram(name, node_names_) for name in node_names_}

    results = run(config=cfg, programs=programs, num_times=1)

    reference_result = results[0][0]["result"]
    for node_result in results:
        node_result = node_result[0]
        print(f"{node_result['name']} measures: {node_result['result']}")
        assert node_result["result"] == reference_result
