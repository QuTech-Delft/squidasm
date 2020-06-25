import logging
import netsquid as ns

from netqasm.logging import set_log_level
from netqasm.parsing import parse_text_subroutine, parse_register
from netqasm.messages import Message, MessageType, InitNewAppMessage
from squidasm.network_setup import get_node
from squidasm.qnodeos import SubroutineHandler
from squidasm.queues import get_queue
from squidasm.run import reset


def test():
    set_log_level(logging.DEBUG)
    alice = get_node(name="Alice")
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
    queue.put(Message(
        type=MessageType.INIT_NEW_APP,
        msg=InitNewAppMessage(
            app_id=app_id,
            max_qubits=1,
        ),
    ))
    # Put the subroutine
    subroutine = parse_text_subroutine(subroutine)
    queue.put(Message(type=MessageType.SUBROUTINE, msg=bytes(subroutine)))

    # Starting subroutine
    subroutine_handler.start()

    # Starting netsquid
    ns.sim_run(1000)

    shared_memory = subroutine_handler._executioner._shared_memories[app_id]
    m = shared_memory.get_register(parse_register("M0"))
    assert m in set([0, 1])
    reset()
