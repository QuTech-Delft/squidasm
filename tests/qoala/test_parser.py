import pytest

from squidasm.qoala.lang.iqoala import (
    AssignCValueOp,
    IqoalaParser,
    IqoalaProgram,
    ParseError,
    ProgramMeta,
)
from squidasm.qoala.runtime.config import GenericQDeviceConfig, LinkConfig
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.run import run


def test_parse_incomplete_meta():
    program_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
META_END
    """

    with pytest.raises(ParseError):
        IqoalaParser(program_text).parse()


def test_parse_meta_no_end():
    program_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
    """

    with pytest.raises(ParseError):
        IqoalaParser(program_text).parse()


def test_parse_meta():
    program_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    parsed = IqoalaParser(program_text).parse()

    assert len(parsed.instructions) == 0
    assert parsed.meta == ProgramMeta(
        name="alice", parameters=[], csockets={0: "bob"}, epr_sockets={}
    )


def test_parse_meta_multiple_remotes():
    program_text = """
META_START
name: alice
parameters: theta1, theta2
csockets: 0 -> bob, 1 -> charlie
epr_sockets: 0 -> bob
META_END
    """

    parsed = IqoalaParser(program_text).parse()

    assert len(parsed.instructions) == 0
    assert parsed.meta == ProgramMeta(
        name="alice",
        parameters=["theta1", "theta2"],
        csockets={0: "bob", 1: "charlie"},
        epr_sockets={0: "bob"},
    )


DEFAULT_META = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
"""


def test_parse_1_instr():
    program_text = DEFAULT_META
    program_text += """
x = assign_cval() : 1
    """

    parsed = IqoalaParser(program_text).parse()

    assert len(parsed.instructions) == 1
    assert parsed.instructions[0] == AssignCValueOp(result="x", value=1)


def test_parse_2_instr():
    program_text = DEFAULT_META
    program_text += """
x = assign_cval() : 1
y = assign_cval() : 17
    """

    parsed = IqoalaParser(program_text).parse()

    assert len(parsed.instructions) == 2
    assert parsed.instructions[0] == AssignCValueOp(result="x", value=1)
    assert parsed.instructions[1] == AssignCValueOp(result="y", value=17)


def test_parse_with_subrt():
    program_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
my_value = assign_cval() : 1
remote_id = assign_cval() : 0
send_cmsg(remote_id, my_value)
received_value = recv_cmsg(remote_id)
new_value = assign_cval() : 3
my_value = add_cval_c(new_value, new_value)
vec<m> = run_subroutine(vec<my_value>) : subrt1
return_result(m)
    """

    subrt_text = """"
SUBROUTINE subrt1
    params: my_value
    returns: M0 -> m
  NETQASM_START
    set Q0 0
    rot_z Q0 {my_value} 4
    meas Q0 M0
    ret_reg M0
  NETQASM_END
    """

    parsed_program = IqoalaParser(program_text).parse()

    print(parsed_program)


if __name__ == "__main__":
    test_parse_incomplete_meta()
    test_parse_meta_no_end()
    test_parse_meta()
    test_parse_meta_multiple_remotes()
    test_parse_1_instr()
    test_parse_2_instr()
    # test_parse_with_subrt()
