import logging

import netsquid as ns
import numpy as np
from netqasm.lang.parsing import parse_register, parse_text_subroutine
from netqasm.logging.glob import set_log_level
from netsquid.nodes import Node
from netsquid.protocols import NodeProtocol

from squidasm.nqasm.executor.vanilla import VanillaNetSquidExecutor
from squidasm.sim.network import QDevice


def test_executor():
    set_log_level(logging.DEBUG)
    subroutine = """
# NETQASM 1.0
# APPID 0
set Q0 0
qalloc Q0
init Q0
h Q0
meas Q0 M0
bez M0 EXIT
x Q0
EXIT:
ret_reg M0
"""
    subroutine = parse_text_subroutine(subroutine)
    app_id = 0
    node = Node("Alice", qmemory=QDevice())
    executor = VanillaNetSquidExecutor(node=node)
    # Consume the generator
    executor.init_new_application(app_id=app_id, max_qubits=1)

    class ExecuteProtocol(NodeProtocol):
        def run(self):
            yield from executor.execute_subroutine(subroutine=subroutine)

    node = Node("node", qmemory=QDevice())
    prot = ExecuteProtocol(node)
    prot.start()
    ns.sim_run()

    shared_memory = executor._shared_memories[app_id]
    m = shared_memory.get_register(parse_register("M0"))
    assert m in set([0, 1])
    qubit = executor._qdevice._get_qubits(0)[0]
    dm = qubit.qstate.qrepr.reduced_dm()
    expected_dm = np.array([[1, 0], [0, 0]])
    assert np.all(np.isclose(dm, expected_dm))
