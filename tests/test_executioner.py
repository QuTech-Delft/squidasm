import logging
import numpy as np
import netsquid as ns
from netsquid.protocols import NodeProtocol
from netsquid.nodes import Node

from netqasm.logging.glob import set_log_level
from netqasm.lang.parsing import parse_text_subroutine, parse_register
from squidasm.executioner.vanilla import VanillaNetSquidExecutioner
from squidasm.network import QDevice
from squidasm.run import reset


def test_executioner():
    set_log_level(logging.DEBUG)
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q Q0
# DEFINE m M0
set q! 0
qalloc q!
init q!
op! q! // this is a comment
meas q! m!
bez m! EXIT
x q!
EXIT:
ret_reg m!
// this is also a comment
"""
    subroutine = parse_text_subroutine(subroutine)
    app_id = 0
    node = Node("Alice", qmemory=QDevice())
    executioner = VanillaNetSquidExecutioner(node=node)
    # Consume the generator
    executioner.init_new_application(app_id=app_id, max_qubits=1)

    class ExecuteProtocol(NodeProtocol):
        def run(self):
            yield from executioner.execute_subroutine(subroutine=subroutine)

    node = Node("node", qmemory=QDevice())
    prot = ExecuteProtocol(node)
    prot.start()
    ns.sim_run()

    shared_memory = executioner._shared_memories[app_id]
    m = shared_memory.get_register(parse_register("M0"))
    assert m in set([0, 1])
    qubit = executioner._qdevice._get_qubits(0)[0]
    dm = qubit.qstate.dm
    expected_dm = np.array([[1, 0], [0, 0]])
    assert np.all(np.isclose(dm, expected_dm))
    reset()
