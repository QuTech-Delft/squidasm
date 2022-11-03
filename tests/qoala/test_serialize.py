import pytest
from netqasm.lang.instr.core import MeasInstruction, SetInstruction
from netqasm.lang.operand import Register, Template
from netqasm.lang.subroutine import Subroutine

from squidasm.qoala.lang.iqoala import (
    AssignCValueOp,
    IqoalaInstrParser,
    IqoalaParseError,
    IqoalaParser,
    IqoalaSharedMemLoc,
    IqoalaSubroutine,
    IQoalaSubroutineParser,
    IqoalaVector,
    ProgramMeta,
    RunSubroutineOp,
)


def text_equal(text1, text2) -> bool:
    # allows whitespace differences
    lines1 = [line.strip() for line in text1.split("\n") if len(line) > 0]
    lines2 = [line.strip() for line in text2.split("\n") if len(line) > 0]
    for line1, line2 in zip(lines1, lines2):
        if line1 != line2:
            return False
    return True


def test_serialize_meta_1():
    expected = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
    """

    meta = ProgramMeta(name="alice", parameters=[], csockets={0: "bob"}, epr_sockets={})
    assert text_equal(meta.serialize(), expected)


def test_serialize_meta_2():
    expected = """
META_START
name: alice
parameters: theta1, theta2
csockets: 0 -> bob, 1 -> charlie
epr_sockets: 1 -> charlie
META_END
    """

    meta = ProgramMeta(
        name="alice",
        parameters=["theta1", "theta2"],
        csockets={0: "bob", 1: "charlie"},
        epr_sockets={1: "charlie"},
    )
    assert text_equal(meta.serialize(), expected)


if __name__ == "__main__":
    test_serialize_meta_1()
    test_serialize_meta_2()
