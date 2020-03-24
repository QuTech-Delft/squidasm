import logging
import numpy as np
import netsquid as ns
from netsquid.protocols import NodeProtocol

from netqasm.parser import Parser
from squidasm.executioner import NetSquidExecutioner
from squidasm.network_setup import get_node


def test_executioner():
    logging.getLogger().setLevel(logging.DEBUG)
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q q0
qalloc q!
init q!
op! q! // this is a comment
meas q! m
beq m 0 EXIT
x q!
EXIT:
// this is also a comment
"""
    subroutine = Parser(subroutine).subroutine
    app_id = 0
    node = get_node("Alice")
    executioner = NetSquidExecutioner(node=node)
    executioner.init_new_application(app_id=app_id, max_qubits=1)

    class ExecuteProtocol(NodeProtocol):
        def run(self):
            yield from executioner.execute_subroutine(subroutine=subroutine)

    prot = ExecuteProtocol(node=get_node("node"))
    prot.start()
    ns.sim_run()

    shared_memory = executioner._shared_memories[app_id]
    assert shared_memory[0] in set([0, 1])
    qubit = executioner._qdevice._get_qubits(0)[0]
    dm = qubit.qstate.dm
    expected_dm = np.array([[1, 0], [0, 0]])
    assert np.all(np.isclose(dm, expected_dm))