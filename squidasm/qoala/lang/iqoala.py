from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Type, Union

from netqasm.lang.instr import NetQASMInstruction
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.operand import Template
from netqasm.lang.parsing.text import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine

IqoalaValue = Union[int, Template]


@dataclass
class ProgramMeta:
    name: str
    parameters: Dict[str, Type]  # input name -> input type
    csockets: Dict[int, str]  # socket ID -> remote node name
    epr_sockets: Dict[int, str]  # socket ID -> remote node name


class IqoalaInstructionType(Enum):
    CC = 0
    CL = auto()
    QC = auto()
    QL = auto()


@dataclass
class IqoalaInstructionSignature:
    typ: IqoalaInstructionType
    duration: int = 0


class StaticIqoalaProgramInfo:
    pass


class DynamicIqoalaProgramInfo:
    pass


class IqoalaAttribute:
    def __init__(self, value: IqoalaValue) -> None:
        self._value = value

    @property
    def value(self) -> IqoalaValue:
        return self._value


class IqoalaSharedMemLoc:
    def __init__(self, loc: str) -> None:
        self._loc = loc

    @property
    def loc(self) -> str:
        return self._loc

    def __str__(self) -> str:
        return str(self.loc)


class IqoalaVector:
    def __init__(self, values: List[str]) -> None:
        self._values = values

    @property
    def values(self) -> List[str]:
        return self._values

    def __str__(self) -> str:
        return f"vec<{','.join(v for v in self.values)}>"


class IqoalaSubroutine:
    def __init__(
        self, subrt: Subroutine, return_map: Dict[str, IqoalaSharedMemLoc]
    ) -> None:
        self._subrt = subrt
        self._return_map = return_map

    @property
    def subroutine(self) -> Subroutine:
        return self._subrt

    @property
    def return_map(self) -> Dict[str, IqoalaSharedMemLoc]:
        return self._return_map

    def __str__(self) -> str:
        s = "\n"
        for key, value in self.return_map.items():
            s += f"return {str(value)} -> {key}\n"
        s += "NETQASM_START\n"
        s += self.subroutine.print_instructions()
        s += "\nNETQASM_END"
        return s


class ClassicalIqoalaOp:
    def __init__(
        self,
        arguments: Optional[List[str]] = None,
        results: Optional[List[str]] = None,
        attributes: Optional[List[IqoalaValue]] = None,
    ) -> None:
        self._arguments: List[str]
        self._results: List[str]
        self._attributes: List[IqoalaValue]

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
    def attributes(self) -> List[IqoalaValue]:
        return self._attributes


class SendCMsgOp(ClassicalIqoalaOp):
    OP_NAME = "send_cmsg"
    TYP = IqoalaInstructionType.CC

    def __init__(self, csocket: str, value: str) -> None:
        # args:
        #   csocket (int): ID of csocket
        #   value (str): ID of csocket
        super().__init__(arguments=[csocket, value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is None
        assert len(args) == 2
        assert attr is None
        return cls(args[0], args[1])


class ReceiveCMsgOp(ClassicalIqoalaOp):
    OP_NAME = "recv_cmsg"
    TYP = IqoalaInstructionType.CC

    def __init__(self, csocket: str, result: str) -> None:
        super().__init__(arguments=[csocket], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is not None
        assert len(args) == 1
        assert attr is None
        return cls(args[0], result)


class AddCValueOp(ClassicalIqoalaOp):
    OP_NAME = "add_cval_c"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value0: str, value1: str) -> None:
        super().__init__(arguments=[value0, value1], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is not None
        assert len(args) == 2
        assert attr is None
        return cls(result, args[0], args[1])


class MultiplyConstantCValueOp(ClassicalIqoalaOp):
    OP_NAME = "mult_const"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value0: str, value1: IqoalaAttribute) -> None:
        super().__init__(arguments=[value0, value1], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is not None
        assert len(args) == 2
        assert attr is None
        return cls(result, args[0], args[1])


class BitConditionalMultiplyConstantCValueOp(ClassicalIqoalaOp):
    OP_NAME = "bcond_mult_const"
    TYP = IqoalaInstructionType.CL

    def __init__(
        self, result: str, value0: str, value1: IqoalaAttribute, cond: str
    ) -> None:
        super().__init__(arguments=[value0, value1, cond], results=[result])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is not None
        assert len(args) == 3
        assert attr is None
        return cls(result, args[0], args[1], args[2])


class AssignCValueOp(ClassicalIqoalaOp):
    OP_NAME = "assign_cval"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value: IqoalaValue) -> None:
        super().__init__(results=[result], attributes=[value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is not None
        assert len(args) == 0
        assert attr is not None
        return cls(result, attr)


class RunSubroutineOp(ClassicalIqoalaOp):
    OP_NAME = "run_subroutine"
    TYP = IqoalaInstructionType.CL

    def __init__(self, values: IqoalaVector, subrt: IqoalaSubroutine) -> None:
        super().__init__(arguments=[values], attributes=[subrt])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is None
        assert len(args) == 1
        assert isinstance(args[0], IqoalaVector)
        assert attr is not None
        return cls(args[0], attr)

    @property
    def subroutine(self) -> IqoalaSubroutine:
        return self.attributes[0]

    def __str__(self) -> str:
        return super().__str__()


class ReturnResultOp(ClassicalIqoalaOp):
    OP_NAME = "return_result"
    TYP = IqoalaInstructionType.CL

    def __init__(self, value: str) -> None:
        super().__init__(arguments=[value])

    @classmethod
    def from_generic_args(cls, result: str, args: List[str], attr: IqoalaValue):
        assert result is None
        assert len(args) == 1
        assert attr is None
        return cls(args[0])


LHR_OP_NAMES = {
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


def netqasm_instr_to_type(instr: NetQASMInstruction) -> IqoalaInstructionType:
    if instr.mnemonic in ["create_epr", "recv_epr"]:
        return IqoalaInstructionType.QC
    else:
        return IqoalaInstructionType.QL


class IqoalaProgram:
    def __init__(
        self,
        instructions: List[ClassicalIqoalaOp],
        subroutines: Dict[str, Subroutine],
        meta: ProgramMeta,
    ) -> None:
        self._instructions: List[ClassicalIqoalaOp] = instructions
        self._subroutines: Dict[str, Subroutine] = subroutines
        self._meta: ProgramMeta = meta

    @property
    def meta(self) -> ProgramMeta:
        return self._meta

    @property
    def instructions(self) -> List[ClassicalIqoalaOp]:
        return self._instructions

    @instructions.setter
    def instructions(self, new_instrs) -> None:
        self._instructions = new_instrs

    def get_instr_signatures(self) -> List[IqoalaInstructionSignature]:
        sigs: List[IqoalaInstructionSignature] = []
        for instr in self.instructions:
            if isinstance(instr, RunSubroutineOp):
                subrt = instr.subroutine
                for nq_instr in subrt.subroutine.instructions:
                    typ = netqasm_instr_to_type(nq_instr)
                    sigs.append(typ)
            else:
                sigs.append(instr.TYP)
        return sigs

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


class EndOfTextException(Exception):
    pass


class IqoalaParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1
        if self._lineno >= len(self._lines):
            raise EndOfTextException

    def _parse_lhr(self) -> ClassicalIqoalaOp:
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
                    vec_values = [x.strip() for x in vec_values_str.split(";")]
                return IqoalaVector(vec_values)
            return arg

        args = [parse_arg(arg) for arg in args]

        # print(f"result = {result}, op = {op}, args = {args}, attr = {attr}")

        lhr_op = LHR_OP_NAMES[op].from_generic_args(result, args, attr)
        return lhr_op

    def _read_line(self) -> str:
        self._next_line()
        return self._lines[self._lineno]

    def _parse_subroutine(self) -> IqoalaSubroutine:
        return_map: Dict[str, IqoalaSharedMemLoc] = {}
        while (line := self._read_line()) != "NETQASM_START":
            ret_text = "return "
            assert line.startswith(ret_text)
            map_text = line[len(ret_text) :]
            map_parts = [x.strip() for x in map_text.split("->")]
            assert len(map_parts) == 2
            shared_loc = map_parts[0]
            variable = map_parts[1]
            return_map[variable] = IqoalaSharedMemLoc(shared_loc)
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
        return IqoalaSubroutine(subrt, return_map)

    def parse(self) -> IqoalaProgram:
        instructions = []
        subroutines = {}

        # TODO: parse ProgramMeta

        try:
            while True:
                instr = self._parse_lhr()
                if isinstance(instr, RunSubroutineOp):
                    subrt = self._parse_subroutine()
                    instr = RunSubroutineOp(instr.arguments[0], subrt)
                instructions.append(instr)
                self._next_line()
        except EndOfTextException:
            pass

        return IqoalaProgram(instructions, subroutines)


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
    lhr_subrt = IqoalaSubroutine(subrt, {"m": IqoalaSharedMemLoc("M0")})
    ops.append(RunSubroutineOp(IqoalaVector(["my_value"]), lhr_subrt))
    ops.append(ReturnResultOp("m"))

    program = IqoalaProgram(
        instructions=ops,
        subroutines={"subrt1": subrt},
    )
    print("original program:")
    print(program)

    text = str(program)
    parsed_program = IqoalaParser(text).parse()

    print("\nto text and parsed back:")
    print(parsed_program)

    print(parsed_program.get_instr_signatures())
