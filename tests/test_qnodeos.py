import logging
import netsquid as ns

from netqasm.parser import Parser
from netqasm.sdk.shared_memory import reset_memories
from squidasm.network_setup import get_node
from squidasm.qnodeos import SubroutineHandler
from squidasm.queues import get_queue, Signal
from squidasm.sdk import Message, MessageType, InitNewAppMessage


def test():
    logging.basicConfig(level=logging.DEBUG)
    reset_memories()
    alice = get_node(name="Alice", num_qubits=5)
    subroutine_handler = SubroutineHandler(alice)

    # Put subroutine in queue
    queue = get_queue(alice.name)
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
    # Initialize the new application
    app_id = 0
    queue.put(Message(type=MessageType.INIT_NEW_APP, msg=InitNewAppMessage(app_id=app_id, max_qubits=1)))
    # Put the subroutine
    subroutine = Parser(subroutine).subroutine
    queue.put(Message(type=MessageType.SUBROUTINE, msg=subroutine))
    # Make sure to signal to stop after
    queue.put(Message(type=MessageType.SIGNAL, msg=Signal.STOP))

    # Starting subroutine
    subroutine_handler.start()

    # Starting netsquid
    ns.sim_run()

    shared_memory = subroutine_handler._executioner._shared_memories[app_id]
    assert shared_memory[0] in set([0, 1])
