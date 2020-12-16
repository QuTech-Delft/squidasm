import logging
import netsquid as ns
from netsquid.nodes import Node

from netqasm.logging.glob import set_log_level
from netqasm.lang.parsing import parse_text_subroutine, parse_register
from netqasm.backend.messages import InitNewAppMessage, SubroutineMessage
from squidasm.network import QDevice
from squidasm.qnodeos import SubroutineHandler
from squidasm.queues import get_queue
from squidasm.run import reset


def test():
    set_log_level(logging.INFO)
    alice = Node(name="Alice", qmemory=QDevice())
    subroutine_handler = SubroutineHandler(alice)

    # Put subroutine in queue
    queue = get_queue(alice.name)
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
    # Initialize the new application
    app_id = 0
    queue.put(
        bytes(InitNewAppMessage(
            app_id=app_id,
            max_qubits=1,
        )),
    )
    # Put the subroutine
    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    queue.put(bytes(SubroutineMessage(subroutine=subroutine)))

    # Starting subroutine
    subroutine_handler.start()

    # Starting netsquid
    ns.sim_run(2e5)

    shared_memory = subroutine_handler._executioner._shared_memories[app_id]
    m = shared_memory.get_register(parse_register("M0"))
    assert m in set([0, 1])
    reset()


if __name__ == "__main__":
    test()
