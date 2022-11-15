import os

import pytest
from netqasm.lang.instr.core import MeasInstruction, SetInstruction
from netqasm.lang.operand import Register, Template
from netqasm.lang.subroutine import Subroutine

from squidasm.qoala.lang.iqoala import (
    AssignCValueOp,
    IqoalaInstrParser,
    IqoalaMetaParser,
    IqoalaParseError,
    IqoalaParser,
    IqoalaSharedMemLoc,
    IqoalaSubroutine,
    IQoalaSubroutineParser,
    IqoalaVector,
    ProgramMeta,
    RunSubroutineOp,
)
from squidasm.util.tests import text_equal


def test_parse_incomplete_meta():
    text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
META_END
    """

    with pytest.raises(IqoalaParseError):
        IqoalaMetaParser(text).parse()


def test_parse_meta_no_end():
    text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
    """

    with pytest.raises(IqoalaParseError):
        IqoalaMetaParser(text).parse()


def test_parse_meta():
    text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    meta = IqoalaMetaParser(text).parse()

    assert meta == ProgramMeta(
        name="alice", parameters=[], csockets={0: "bob"}, epr_sockets={}
    )


def test_parse_meta_multiple_remotes():
    text = """
META_START
name: alice
parameters: theta1, theta2
csockets: 0 -> bob, 1 -> charlie
epr_sockets: 0 -> bob
META_END
    """

    meta = IqoalaMetaParser(text).parse()

    assert meta == ProgramMeta(
        name="alice",
        parameters=["theta1", "theta2"],
        csockets={0: "bob", 1: "charlie"},
        epr_sockets={0: "bob"},
    )


def test_parse_1_instr():
    text = """
x = assign_cval() : 1
    """

    instructions = IqoalaInstrParser(text).parse()

    assert len(instructions) == 1
    assert instructions[0] == AssignCValueOp(result="x", value=1)


def test_parse_2_instr():
    text = """
x = assign_cval() : 1
y = assign_cval() : 17
    """

    instructions = IqoalaInstrParser(text).parse()

    assert len(instructions) == 2
    assert instructions[0] == AssignCValueOp(result="x", value=1)
    assert instructions[1] == AssignCValueOp(result="y", value=17)


def test_parse_faulty_instr():
    text = """
x = assign_cval
    """

    with pytest.raises(IqoalaParseError):
        IqoalaInstrParser(text).parse()


def test_parse_vec():
    text = """
run_subroutine(vec<x>) : subrt1
    """

    instructions = IqoalaInstrParser(text).parse()
    assert len(instructions) == 1
    assert instructions[0] == RunSubroutineOp(
        result=None, values=IqoalaVector(["x"]), subrt="subrt1"
    )


def test_parse_vec_2_elements():
    text = """
run_subroutine(vec<x; y>) : subrt1
    """

    instructions = IqoalaInstrParser(text).parse()
    assert len(instructions) == 1
    assert instructions[0] == RunSubroutineOp(
        result=None, values=IqoalaVector(["x", "y"]), subrt="subrt1"
    )


def test_parse_vec_2_elements_and_return():
    text = """
vec<m> = run_subroutine(vec<x; y>) : subrt1
    """

    instructions = IqoalaInstrParser(text).parse()
    assert len(instructions) == 1
    assert instructions[0] == RunSubroutineOp(
        result=IqoalaVector(["m"]), values=IqoalaVector(["x", "y"]), subrt="subrt1"
    )


def test_parse_vec_2_elements_and_return_2_elements():
    text = """
vec<m1; m2> = run_subroutine(vec<x; y>) : subrt1
    """

    instructions = IqoalaInstrParser(text).parse()
    assert len(instructions) == 1
    assert instructions[0] == RunSubroutineOp(
        result=IqoalaVector(["m1", "m2"]),
        values=IqoalaVector(["x", "y"]),
        subrt="subrt1",
    )


def test_parse_subrt():
    text = """
SUBROUTINE subrt1
    params: my_value
    returns: M0 -> m
  NETQASM_START
    set Q0 {my_value}
  NETQASM_END
    """

    parsed = IQoalaSubroutineParser(text).parse()
    assert len(parsed) == 1
    assert "subrt1" in parsed
    subrt = parsed["subrt1"]

    expected_instrs = [
        SetInstruction(reg=Register.from_str("Q0"), imm=Template("my_value"))
    ]
    expected_args = ["my_value"]
    assert subrt == IqoalaSubroutine(
        name="subrt1",
        subrt=Subroutine(instructions=expected_instrs, arguments=expected_args),
        return_map={"m": IqoalaSharedMemLoc("M0")},
    )


def test_parse_subrt_2():
    text = """
SUBROUTINE my_subroutine
    params: param1, param2
    returns: M5 -> result1, M6 -> result2
  NETQASM_START
    set R0 {param1}
    set R1 {param2}
    meas Q0 M5
    meas Q1 M6
  NETQASM_END
    """

    parsed = IQoalaSubroutineParser(text).parse()
    assert len(parsed) == 1
    assert "my_subroutine" in parsed
    subrt = parsed["my_subroutine"]

    expected_instrs = [
        SetInstruction(reg=Register.from_str("R0"), imm=Template("param1")),
        SetInstruction(reg=Register.from_str("R1"), imm=Template("param2")),
        MeasInstruction(reg0=Register.from_str("Q0"), reg1=Register.from_str("M5")),
        MeasInstruction(reg0=Register.from_str("Q1"), reg1=Register.from_str("M6")),
    ]
    expected_args = ["param1", "param2"]
    assert subrt == IqoalaSubroutine(
        name="my_subroutine",
        subrt=Subroutine(instructions=expected_instrs, arguments=expected_args),
        return_map={
            "result1": IqoalaSharedMemLoc("M5"),
            "result2": IqoalaSharedMemLoc("M6"),
        },
    )


def test_parse_multiple_subrt():
    text = """
SUBROUTINE subrt1
    params: param1
    returns: M0 -> m
  NETQASM_START
    set R0 {param1}
    meas Q0 M0
  NETQASM_END

SUBROUTINE subrt2
    params: theta
    returns: 
  NETQASM_START
    set R0 {theta}
  NETQASM_END
    """

    parsed = IQoalaSubroutineParser(text).parse()
    assert len(parsed) == 2
    assert "subrt1" in parsed
    assert "subrt2" in parsed
    subrt1 = parsed["subrt1"]
    subrt2 = parsed["subrt2"]

    expected_instrs_1 = [
        SetInstruction(reg=Register.from_str("R0"), imm=Template("param1")),
        MeasInstruction(reg0=Register.from_str("Q0"), reg1=Register.from_str("M0")),
    ]
    expected_args_1 = ["param1"]
    expected_instrs_2 = [
        SetInstruction(reg=Register.from_str("R0"), imm=Template("theta")),
    ]
    expected_args_2 = ["theta"]

    assert subrt1 == IqoalaSubroutine(
        name="subrt1",
        subrt=Subroutine(instructions=expected_instrs_1, arguments=expected_args_1),
        return_map={
            "m": IqoalaSharedMemLoc("M0"),
        },
    )
    assert subrt2 == IqoalaSubroutine(
        name="subrt2",
        subrt=Subroutine(instructions=expected_instrs_2, arguments=expected_args_2),
        return_map={},
    )


def test_parse_invalid_subrt():
    text = """
SUBROUTINE my_subroutine
    params: param1, param2
    returns: M5 -> result1, M6 -> result2
  NETQASM_START
    set R0 {param3}
  NETQASM_END
    """

    with pytest.raises(IqoalaParseError):
        IQoalaSubroutineParser(text).parse()


DEFAULT_META = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
"""


def test_parse_program():
    meta_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    program_text = """
my_value = assign_cval() : 1
remote_id = assign_cval() : 0
send_cmsg(remote_id, my_value)
received_value = recv_cmsg(remote_id)
new_value = assign_cval() : 3
my_value = add_cval_c(new_value, new_value)
vec<m> = run_subroutine(vec<my_value>) : subrt1
return_result(m)
    """

    subrt_text = """
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

    parsed_program = IqoalaParser(
        meta_text=meta_text, instr_text=program_text, subrt_text=subrt_text
    ).parse()
    assert len(parsed_program.instructions) == 8
    assert "subrt1" in parsed_program.subroutines


def test_parse_program_invalid_subrt_reference():
    meta_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    program_text = """
my_value = assign_cval() : 1
vec<m> = run_subroutine(vec<my_value>) : non_existing_subrt
return_result(m)
    """

    subrt_text = """
SUBROUTINE subrt1
    params: my_value
    returns: M0 -> m
  NETQASM_START
    set R0 0
  NETQASM_END
    """

    with pytest.raises(IqoalaParseError):
        IqoalaParser(
            meta_text=meta_text, instr_text=program_text, subrt_text=subrt_text
        ).parse()


def test_split_text():
    meta_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    instr_text = """
m = assign_cval() : 1
return_result(m)
    """

    subrt_text = """
SUBROUTINE subrt1
    params: 
    returns: 
  NETQASM_START
    set Q0 0
  NETQASM_END
    """

    text = meta_text + instr_text + subrt_text
    parser = IqoalaParser(text)

    assert text_equal(parser._meta_text, meta_text)
    assert text_equal(parser._instr_text, instr_text)
    assert text_equal(parser._subrt_text, subrt_text)


def test_split_text_multiple_subroutines():
    meta_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    instr_text = """
m = assign_cval() : 1
return_result(m)
    """

    subrt_text = """
SUBROUTINE subrt1
    params: 
    returns: 
  NETQASM_START
    set Q0 0
  NETQASM_END

SUBROUTINE subrt2
    params: 
    returns: 
  NETQASM_START
    set Q7 7
  NETQASM_END
    """

    text = meta_text + instr_text + subrt_text
    parser = IqoalaParser(text)

    assert text_equal(parser._meta_text, meta_text)
    assert text_equal(parser._instr_text, instr_text)
    assert text_equal(parser._subrt_text, subrt_text)


def test_parse_program_single_text():
    text = """
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

    parsed_program = IqoalaParser(text).parse()
    assert len(parsed_program.instructions) == 8
    assert "subrt1" in parsed_program.subroutines


def test_parse_file():
    path = os.path.join(os.path.dirname(__file__), "program.iqoala")
    with open(path) as file:
        text = file.read()
    parsed_program = IqoalaParser(text).parse()
    assert len(parsed_program.instructions) == 11
    assert "create_epr_1" in parsed_program.subroutines
    assert "create_epr_2" in parsed_program.subroutines
    assert "local_cphase" in parsed_program.subroutines
    assert "meas_qubit_1" in parsed_program.subroutines
    assert "meas_qubit_2" in parsed_program.subroutines


if __name__ == "__main__":
    # test_parse_incomplete_meta()
    # test_parse_meta_no_end()
    # test_parse_meta()
    # test_parse_meta_multiple_remotes()
    # test_parse_1_instr()
    # test_parse_2_instr()
    # test_parse_faulty_instr()
    # test_parse_vec()
    # test_parse_vec_2_elements()
    # test_parse_vec_2_elements_and_return()
    # test_parse_vec_2_elements_and_return_2_elements()
    # test_parse_subrt()
    # test_parse_subrt_2()
    # test_parse_invalid_subrt()
    # test_parse_multiple_subrt()
    # test_parse_program()
    # test_parse_program_invalid_subrt_reference()
    # test_split_text()
    # test_split_text_multiple_subroutines()
    # test_parse_program_single_text()
    test_parse_file()
