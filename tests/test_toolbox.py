from functools import partial

from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications
from netqasm.sdk.toolbox import create_ghz


def _gen_create_ghz(num_nodes):

    outcomes = {}

    def run_node(node, down_node=None, up_node=None):
        # Setup EPR sockets, depending on the role of the node
        epr_sockets = []
        if down_node is not None:
            down_epr_socket = EPRSocket(down_node)
            epr_sockets.append(down_epr_socket)
        else:
            down_epr_socket = None
        if up_node is not None:
            up_epr_socket = EPRSocket(up_node)
            epr_sockets.append(up_epr_socket)
        else:
            up_epr_socket = None

        with NetSquidConnection(node, epr_sockets=epr_sockets):
            # Create a GHZ state with the other nodes
            q, corr = create_ghz(
                down_epr_socket=down_epr_socket,
                up_epr_socket=up_epr_socket,
            )
            m = q.measure()

        outcomes[node] = (m, corr)

    # Setup the applications
    applications = {}
    for i in range(num_nodes):
        node = f'node{i}'
        if i == 0:
            down_node = None
        else:
            down_node = f'node{i - 1}'
        if i == num_nodes - 1:
            up_node = None
        else:
            up_node = f'node{i + 1}'
        applications[node] = partial(
            run_node,
            node=node,
            down_node=down_node,
            up_node=up_node,
        )

    # Run the applications
    run_applications(applications)

    corrected_outcomes = []
    # Check the outcomes
    correction = 0
    for i in range(num_nodes):
        node = f'node{i}'
        m, corr = outcomes[node]
        corrected_outcome = (m + correction) % 2
        corrected_outcomes.append(corrected_outcome)

        if 0 < i < num_nodes - 1:
            correction = (correction + corr) % 2

    assert len(set(corrected_outcomes)) == 1


def test_create_ghz():
    num = 10
    max_num_node = 5
    for num_nodes in range(2, max_num_node + 1):
        for _ in range(num):
            _gen_create_ghz(num_nodes)


if __name__ == "__main__":
    test_create_ghz()
