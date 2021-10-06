import logging

import netsquid as ns
from netqasm.backend.messages import InitNewAppMessage, SubroutineMessage
from netqasm.lang.parsing import parse_register, parse_text_subroutine
from netqasm.logging.glob import set_log_level
from netqasm.sdk.shared_memory import SharedMemoryManager
from netsquid.nodes import Node

from squidasm.nqasm.qnodeos import SubroutineHandler
from squidasm.sim.network import QDevice
from squidasm.sim.queues import QueueManager


def test():
    set_log_level(logging.INFO)
    SharedMemoryManager.reset_memories()

    alice = Node(name="Alice", qmemory=QDevice())
    subroutine_handler = SubroutineHandler(alice)

    # Put subroutine in queue
    queue = QueueManager.get_queue(alice.name)
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q Q0
# DEFINE m M0
set $q 0
qalloc $q
init $q
$op $q // this is a comment
meas $q $m
bez $m EXIT
x $q
EXIT:
ret_reg $m
// this is also a comment
"""
    # Initialize the new application
    app_id = 0
    queue.put(
        bytes(
            InitNewAppMessage(
                app_id=app_id,
                max_qubits=1,
            )
        ),
    )
    # Put the subroutine
    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    queue.put(bytes(SubroutineMessage(subroutine=subroutine)))

    # Starting subroutine
    subroutine_handler.start()

    # Starting netsquid
    ns.sim_run(5e5)

    shared_memory = subroutine_handler._executor._shared_memories[app_id]
    m = shared_memory.get_register(parse_register("M0"))
    assert m in set([0, 1])


if __name__ == "__main__":
    test()
