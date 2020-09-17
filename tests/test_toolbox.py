import pytest
# from functools import partial

from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection
from squidasm.run import run_applications
from squidasm.run.app_config import AppConfig
from netqasm.sdk.toolbox import create_ghz


def _gen_create_ghz(num_nodes, do_corrections=False):

    outcomes = {}

    def run_node(node, down_node=None, up_node=None):
        # Setup EPR sockets, depending on the role of the node
        epr_sockets = []
        down_epr_socket = None
        down_socket = None
        up_epr_socket = None
        up_socket = None
        if down_node is not None:
            down_epr_socket = EPRSocket(down_node)
            epr_sockets.append(down_epr_socket)
            if do_corrections:
                down_socket = Socket(node, down_node)
        if up_node is not None:
            up_epr_socket = EPRSocket(up_node)
            epr_sockets.append(up_epr_socket)
            if do_corrections:
                up_socket = Socket(node, up_node)

        with NetSquidConnection(node, epr_sockets=epr_sockets):
            # Create a GHZ state with the other nodes
            q, corr = create_ghz(
                down_epr_socket=down_epr_socket,
                up_epr_socket=up_epr_socket,
                down_socket=down_socket,
                up_socket=up_socket,
                do_corrections=do_corrections,
            )
            m = q.measure()

        outcomes[node] = (int(m), int(corr))

    # Setup the applications
    applications = []
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
        applications += [AppConfig(
            app_name=node,
            node_name=node,
            main_func=run_node,
            log_config=None,
            inputs={
                'node': node,
                'down_node': down_node,
                'up_node': up_node,
            }
        )]

    # Run the applications
    run_applications(applications, use_app_config=False)

    if do_corrections:
        corrected_outcomes = [m for (m, _) in outcomes.values()]
    else:
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

    print(corrected_outcomes)

    assert len(set(corrected_outcomes)) == 1


@pytest.mark.parametrize('do_corrections', [True, False])
@pytest.mark.parametrize('num_nodes', range(2, 6))
def test_create_ghz(do_corrections, num_nodes):
    num = 10
    for _ in range(num):
        _gen_create_ghz(num_nodes, do_corrections)
