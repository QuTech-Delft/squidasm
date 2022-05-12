import abc
from typing import Dict, List, Optional, Union

from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.operand import Template
from netqasm.lang.parsing.text import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.sdk.futures import Future

from squidasm.sim.stack.program import ProgramContext, ProgramMeta

LhrValue = Union[int, Template, Future]


class LhrAttribute:
    def __init__(self, value: LhrValue) -> None:
        self._value = value

    @property
    def value(self) -> LhrValue:
        return self._value


class LhrSharedMemLoc:
    def __init__(self, loc: str) -> None:
        self._loc = loc

    @property
    def loc(self) -> str:
        return self._loc

    def __str__(self) -> str:
        return str(self.loc)


class LhrVector:
    def __init__(self, values: List[str]) -> None:
        self._values = values

    @property
    def values(self) -> List[str]:
        return self._values

    def __str__(self) -> str:
        return f"vec<{','.join(v for v in self.values)}>"


class LhrSubroutine:
    def __init__(
        self, subrt: Subroutine, return_map: Dict[str, LhrSharedMemLoc]
    ) -> None:
        self._subrt = subrt
        self._return_map = return_map

    @property
    def subroutine(self) -> Subroutine:
        return self._subrt

    @property
    def return_map(self) -> Dict[str, LhrSharedMemLoc]:
        return self._return_map

    def __str__(self) -> str:
        s = "\n"
        for key, value in self.return_map.items():
            s += f"return {str(value)} -> {key}\n"
        s += "NETQASM_START\n"
        s += self.subroutine.print_instructions()
        s += "\nNETQASM_END"
        return s


class ClassicalLhrOp:
    def __init__(
        self,
        arguments: Optional[List[str]] = None,
        results: Optional[List[str]] = None,
        attributes: Optional[List[LhrValue]] = None,
    ) -> None:
        self._arguments: List[str]
        self._results: List[str]
        self._attributes: List[LhrValue]

        if arguments is None:
            self._arguments = []
        else:
            self._arguments = arguments

        if results is None:
            self._results = []
        else:
            self._results = results

        if attributes is None:
            self._attributes = []
        else:
            self._attributes = attributes

    def __str__(self) -> str:
        results = ", ".join(str(r) for r in self.results)
        args = ", ".join(str(a) for a in self.arguments)
        attrs = ", ".join(str(a) for a in self.attributes)
        s = ""
        if len(results) > 0:
            s += f"{results} = "

        s += f"{self.op_name}({args})"

        if len(attrs) > 0:
            s += f" : {attrs}"
        return s

    @property
    def op_name(self) -> str:
        return self.__class__.OP_NAME

    @property
    def arguments(self) -> List[str]:
        return self._arguments

    @property
    def results(self) -> List[str]:
        return self._results

    @property
    def attributes(self) -> List[LhrValue]:
        return self._attributes


class SendCMsgOp(ClassicalLhrOp):
    OP_NAME = "send_cmsg"

    def __init__(self, value: str) -> None:
        super().__init__(arguments=[value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is None
        assert len(args) == 1
        assert attr is None
        return cls(args[0])


class ReceiveCMsgOp(ClassicalLhrOp):
    OP_NAME = "recv_cmsg"

    def __init__(self, result: str) -> None:
        super().__init__(results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is not None
        assert len(args) == 0
        assert attr is None
        return cls(result)


class AddCValueOp(ClassicalLhrOp):
    OP_NAME = "add_cval_c"

    def __init__(self, result: str, value0: str, value1: str) -> None:
        super().__init__(arguments=[value0, value1], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is not None
        assert len(args) == 2
        assert attr is None
        return cls(result, args[0], args[1])


class MultiplyConstantCValueOp(ClassicalLhrOp):
    OP_NAME = "mult_const"

    def __init__(self, result: str, value0: str, value1: LhrAttribute) -> None:
        super().__init__(arguments=[value0, value1], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is not None
        assert len(args) == 2
        assert attr is None
        return cls(result, args[0], args[1])


class BitConditionalMultiplyConstantCValueOp(ClassicalLhrOp):
    OP_NAME = "bcond_mult_const"

    def __init__(
        self, result: str, value0: str, value1: LhrAttribute, cond: str
    ) -> None:
        super().__init__(arguments=[value0, value1, cond], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is not None
        assert len(args) == 3
        assert attr is None
        return cls(result, args[0], args[1], args[2])


class AssignCValueOp(ClassicalLhrOp):
    OP_NAME = "assign_cval"

    def __init__(self, result: str, value: LhrValue) -> None:
        super().__init__(results=[result], attributes=[value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is not None
        assert len(args) == 0
        assert attr is not None
        return cls(result, attr)


class RunSubroutineOp(ClassicalLhrOp):
    OP_NAME = "run_subroutine"

    def __init__(self, values: LhrVector, subrt: LhrSubroutine) -> None:
        super().__init__(arguments=[values], attributes=[subrt])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is None
        assert len(args) == 1
        assert isinstance(args[0], LhrVector)
        assert attr is not None
        return cls(args[0], attr)

    def __str__(self) -> str:
        return super().__str__()


class ReturnResultOp(ClassicalLhrOp):
    OP_NAME = "return_result"

    def __init__(self, value: str) -> None:
        super().__init__(arguments=[value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: LhrValue):
        assert result is None
        assert len(args) == 1
        assert attr is None
        return cls(args[0])


LIR_OP_NAMES = {
    cls.OP_NAME: cls
    for cls in [
        SendCMsgOp,
        ReceiveCMsgOp,
        AddCValueOp,
        MultiplyConstantCValueOp,
        BitConditionalMultiplyConstantCValueOp,
        AssignCValueOp,
        RunSubroutineOp,
        ReturnResultOp,
    ]
}


class LhrProgram:
    def __init__(
        self,
        instructions: List[ClassicalLhrOp],
        subroutines: Dict[str, Subroutine],
        meta: Optional[ProgramMeta] = None,
    ) -> None:
        self._instructions: List[ClassicalLhrOp] = instructions
        self._subroutines: Dict[str, Subroutine] = subroutines
        self._meta: Optional[ProgramMeta] = meta

    @property
    def meta(self) -> ProgramMeta:
        if self._meta is None:
            raise NotImplementedError
        return self._meta

    @meta.setter
    def meta(self, new_meta: ProgramMeta) -> None:
        self._meta = new_meta

    @property
    def instructions(self) -> List[ClassicalLhrOp]:
        return self._instructions

    @instructions.setter
    def instructions(self, new_instrs) -> None:
        self._instructions = new_instrs

    @property
    def subroutines(self) -> Dict[str, Subroutine]:
        return self._subroutines

    @subroutines.setter
    def subroutines(self, new_subroutines) -> None:
        self._subroutines = new_subroutines

    def __str__(self) -> str:
        # instrs = [
        #     f"{str(i)}\n{self.subroutines[i.arguments[0]]}"  # inline subroutine contents
        #     if isinstance(i, RunSubroutineOp)
        #     else str(i)
        #     for i in self.instructions
        # ]

        # return "\n".join("  " + i for i in instrs)
        return "\n".join("  " + str(i) for i in self.instructions)

    def compile(self, context: ProgramContext) -> None:
        raise NotImplementedError


class EndOfTextException(Exception):
    pass


class LhrParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1
        if self._lineno >= len(self._lines):
            raise EndOfTextException

    def _parse_lir(self) -> ClassicalLhrOp:
        line = self._lines[self._lineno]

        assign_parts = [x.strip() for x in line.split("=")]
        assert len(assign_parts) <= 2
        if len(assign_parts) == 1:
            value = assign_parts[0]
            result = None
        elif len(assign_parts) == 2:
            value = assign_parts[1]
            result = assign_parts[0]
        value_parts = [x.strip() for x in value.split(":")]
        assert len(value_parts) <= 2
        if len(value_parts) == 2:
            value = value_parts[0]
            attr = value_parts[1]
            try:
                attr = int(attr)
            except ValueError:
                pass
        else:
            value = value_parts[0]
            attr = None

        op_parts = [x.strip() for x in value.split("(")]
        assert len(op_parts) == 2
        op = op_parts[0]
        arguments = op_parts[1].rstrip(")")
        if len(arguments) == 0:
            args = []
        else:
            args = [x.strip() for x in arguments.split(",")]

        def parse_arg(arg):
            if arg.startswith("vec<"):
                vec_values_str = arg[4:-1]
                if len(vec_values_str) == 0:
                    vec_values = []
                else:
                    vec_values = [x.strip() for x in vec_values_str.split(",")]
                return LhrVector(vec_values)
            return arg

        args = [parse_arg(arg) for arg in args]

        # print(f"result = {result}, op = {op}, args = {args}, attr = {attr}")

        lir_op = LIR_OP_NAMES[op].from_generic_args(result, args, attr)
        return lir_op

    def _read_line(self) -> str:
        self._next_line()
        return self._lines[self._lineno]

    def _parse_subroutine(self) -> LhrSubroutine:
        return_dict: Dict[str, LhrSharedMemLoc] = {}
        while (line := self._read_line()) != "NETQASM_START":
            ret_text = "return "
            assert line.startswith(ret_text)
            map_text = line[len(ret_text) :]
            map_parts = [x.strip() for x in map_text.split("->")]
            assert len(map_parts) == 2
            shared_loc = map_parts[0]
            variable = map_parts[1]
            return_dict[variable] = LhrSharedMemLoc(shared_loc)
        subrt_lines = []
        while True:
            line = self._read_line()
            if line == "NETQASM_END":
                break
            subrt_lines.append(line)
        subrt_text = "\n".join(subrt_lines)
        try:
            subrt = parse_text_subroutine(subrt_text)
        except KeyError:
            subrt = parse_text_subroutine(subrt_text, flavour=NVFlavour())
        return LhrSubroutine(subrt, return_dict)

    def parse(self) -> LhrProgram:
        instructions = []
        subroutines = {}

        try:
            while True:
                instr = self._parse_lir()
                if isinstance(instr, RunSubroutineOp):
                    subrt = self._parse_subroutine()
                    instr = RunSubroutineOp(instr.arguments[0], subrt)
                instructions.append(instr)
                self._next_line()
        except EndOfTextException:
            pass

        return LhrProgram(instructions, subroutines)


class SdkProgram(abc.ABC):
    @property
    def meta(self) -> ProgramMeta:
        raise NotImplementedError

    def compile(self, context: ProgramContext) -> LhrProgram:
        raise NotImplementedError


if __name__ == "__main__":
    ops = []
    ops.append(SendCMsgOp("my_value"))
    ops.append(ReceiveCMsgOp("received_value"))
    ops.append(AssignCValueOp("new_value", 3))
    ops.append(AddCValueOp("my_value", "new_value", "new_value"))

    subrt_text = """
    set Q0 0
    rot_z Q0 {my_value} 4
    meas Q0 M0
    ret_reg M0
    """
    subrt = parse_text_subroutine(subrt_text)
    lhr_subrt = LhrSubroutine(subrt, {"m": LhrSharedMemLoc("M0")})
    ops.append(RunSubroutineOp(LhrVector(["my_value"]), lhr_subrt))
    ops.append(ReturnResultOp("m"))

    program = LhrProgram(
        instructions=ops,
        subroutines={"subrt1": subrt},
    )
    print("original program:")
    print(program)

    text = str(program)
    parsed_program = LhrParser(text).parse()

    print("\nto text and parsed back:")
    print(parsed_program)
