import logging

from squidasm.processor import FromStringNetSquidProcessor


def test_processor():
    logging.getLogger().setLevel(logging.DEBUG)
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q @0
creg(1) m
qreg(1) q!
init q!
op! q! // this is a comment
meas q! m
beq m[0] 0 EXIT
x q!
EXIT:
// this is also a comment
"""

    nq_processor = FromStringNetSquidProcessor(subroutine=subroutine)
    nq_processor.execute_next_subroutine()
