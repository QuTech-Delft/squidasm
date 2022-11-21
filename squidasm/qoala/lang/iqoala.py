from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from lib2to3.pgen2.parse import ParseError
from typing import Dict, List, Optional, Tuple, Union

from netqasm.lang.instr import NetQASMInstruction
from netqasm.lang.instr.flavour import NVFlavour
from netqasm.lang.operand import Template
from netqasm.lang.parsing.text import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine

from squidasm.qoala.sim.requests import (
    EprCreateRole,
    EprCreateType,
    NetstackCreateRequest,
    NetstackReceiveRequest,
    T_NetstackRequest,
)


@dataclass
class ProgramMeta:
    name: str
    parameters: List[str]  # list of parameter names (all have type int)
    csockets: Dict[int, str]  # socket ID -> remote node name
    epr_sockets: Dict[int, str]  # socket ID -> remote node name

    @classmethod
    def empty(cls, name: str) -> ProgramMeta:
        return ProgramMeta(name=name, parameters=[], csockets={}, epr_sockets={})

    def serialize(self) -> str:
        s = "META_START"
        s += f"\nname: {self.name}"
        s += f"\nparameters: {', '.join(self.parameters)}"
        s += f"\ncsockets: {', '.join(f'{k} -> {v}' for k,v in self.csockets.items())}"
        s += f"\nepr_sockets: {', '.join(f'{k} -> {v}' for k,v in self.epr_sockets.items())}"
        s += "\nMETA_END"
        return s


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


class IqoalaSubroutine:
    def __init__(
        self,
        name: str,
        subrt: Subroutine,
        return_map: Dict[str, IqoalaSharedMemLoc],
        request_name: Optional[str] = None,
    ) -> None:
        self._name = name
        self._subrt = subrt
        self._return_map = return_map
        self._request_name = request_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def subroutine(self) -> Subroutine:
        return self._subrt

    @property
    def return_map(self) -> Dict[str, IqoalaSharedMemLoc]:
        return self._return_map

    @property
    def request_name(self) -> Optional[str]:
        return self._request_name

    @property
    def subroutine(self) -> Subroutine:
        return self._subrt

    def serialize(self) -> str:
        s = f"SUBROUTINE {self.name}"
        s += f"\nparams: {', '.join(self.subroutine.arguments)}"
        rm = self.return_map  # just to make next line fit on one line
        s += f"\nreturns: {', '.join(f'{v} -> {k}' for k, v in rm.items())}"
        s += "\nNETQASM_START\n"
        s += self.subroutine.print_instructions()
        s += "\nNETQASM_END"
        return s

    def __str__(self) -> str:
        s = "\n"
        for key, value in self.return_map.items():
            s += f"return {str(value)} -> {key}\n"
        s += "NETQASM_START\n"
        s += self.subroutine.print_instructions()
        s += "\nNETQASM_END"
        return s

    def __eq__(self, other: IqoalaSubroutine) -> bool:
        return (
            self.name == other.name
            and self.subroutine == other.subroutine
            and self.return_map == other.return_map
        )


class IqoalaRequest:
    def __init__(
        self, name: str, role: EprCreateRole, request: T_NetstackRequest
    ) -> None:
        self._name = name
        self._role = role
        self._request = request

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> str:
        return self._role

    @property
    def request(self) -> T_NetstackRequest:
        return self._request

    def serialize(self) -> str:
        s = f"REQUEST {self.name}"
        s += f"role: {self.role}"
        s += f"remote_id: {self.request.remote_id}"
        s += f"epr_socket_id: {self.request.epr_socket_id}"
        s += f"typ: {self.request.typ.name}"
        s += f"num_pairs: {self.request.num_pairs}"
        s += f"fidelity: {self.request.fidelity}"
        s += f"virt_qubit_ids: {','.join(self.request.virt_qubit_ids)}"
        s += f"result_array_addr: {self.request.result_array_addr}"
        return s

    def __str__(self) -> str:
        return self.serialize()

    def __eq__(self, other: IqoalaRequest) -> bool:
        return (
            self.name == other.name
            and self.role == other.role
            and self.request == other.request
        )


IqoalaValue = Union[int, Template, str]


class IqoalaAttribute:
    def __init__(self, value: IqoalaValue) -> None:
        self._value = value

    @property
    def value(self) -> IqoalaValue:
        return self._value


@dataclass(eq=True, frozen=True)
class IqoalaSharedMemLoc:
    loc: str

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

    def __eq__(self, other: IqoalaVector) -> bool:
        return self.values == other.values


class ClassicalIqoalaOp:
    OP_NAME: str = None  # type: ignore
    TYP: IqoalaInstructionType = None  # type: ignore

    def __init__(
        self,
        arguments: Optional[Union[List[str], List[IqoalaVector]]] = None,
        results: Optional[List[str]] = None,
        attributes: Optional[List[IqoalaValue]] = None,
    ) -> None:
        # TODO: support list of strs and vectors
        # currently not needed and confuses mypy
        self._arguments: Union[List[str], List[IqoalaVector]]
        self._results: List[str]
        self._attributes: List[IqoalaValue]

        if arguments is None:
            self._arguments = []  # type: ignore
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

    def __eq__(self, other: ClassicalIqoalaOp) -> bool:
        return (
            self.results == other.results
            and self.arguments == other.arguments
            and self.attributes == other.attributes
        )

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ) -> ClassicalIqoalaOp:
        raise NotImplementedError

    @property
    def op_name(self) -> str:
        return self.__class__.OP_NAME  # type: ignore

    @property
    def arguments(self) -> Union[List[str], List[IqoalaVector]]:
        return self._arguments

    @property
    def results(self) -> List[str]:
        return self._results

    @property
    def attributes(self) -> List[IqoalaValue]:
        return self._attributes


class AssignCValueOp(ClassicalIqoalaOp):
    OP_NAME = "assign_cval"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value: IqoalaValue) -> None:
        super().__init__(results=[result], attributes=[value])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        assert result is not None
        assert len(args) == 0
        assert attr is not None
        return cls(result, attr)


class SendCMsgOp(ClassicalIqoalaOp):
    OP_NAME = "send_cmsg"
    TYP = IqoalaInstructionType.CC

    def __init__(self, csocket: str, value: str) -> None:
        # args:
        #   csocket (int): ID of csocket
        #   value (str): name of variable holding the value to send
        super().__init__(arguments=[csocket, value])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
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
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
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
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        assert result is not None
        assert len(args) == 2
        assert attr is None
        return cls(result, args[0], args[1])


class MultiplyConstantCValueOp(ClassicalIqoalaOp):
    OP_NAME = "mult_const"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value0: str, const: IqoalaValue) -> None:
        # result = value0 * const
        super().__init__(arguments=[value0], attributes=[const], results=[result])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        assert result is not None
        assert len(args) == 1
        assert attr is not None
        return cls(result, args[0], attr)


class BitConditionalMultiplyConstantCValueOp(ClassicalIqoalaOp):
    OP_NAME = "bcond_mult_const"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: str, value0: str, cond: str, const: IqoalaValue) -> None:
        # if const == 1:
        #   result = value0 * const
        # else:
        #   result = value0
        super().__init__(arguments=[value0, cond], attributes=[const], results=[result])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        assert result is not None
        assert len(args) == 2
        assert attr is not None
        return cls(result, args[0], args[1], attr)


class RunSubroutineOp(ClassicalIqoalaOp):
    OP_NAME = "run_subroutine"
    TYP = IqoalaInstructionType.CL

    def __init__(self, result: IqoalaVector, values: IqoalaVector, subrt: str) -> None:
        super().__init__(results=[result], arguments=[values], attributes=[subrt])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        if result is not None:
            assert isinstance(result, IqoalaVector)
        assert len(args) == 1
        assert isinstance(args[0], IqoalaVector)
        assert isinstance(attr, str)
        return cls(result, args[0], attr)

    @property
    def subroutine(self) -> str:
        assert isinstance(self.attributes[0], str)
        return self.attributes[0]

    def __str__(self) -> str:
        return super().__str__()


class ReturnResultOp(ClassicalIqoalaOp):
    OP_NAME = "return_result"
    TYP = IqoalaInstructionType.CL

    def __init__(self, value: str) -> None:
        super().__init__(arguments=[value])

    @classmethod
    def from_generic_args(
        cls, result: Optional[str], args: List[str], attr: Optional[IqoalaValue]
    ):
        assert result is None
        assert len(args) == 1
        assert attr is None
        return cls(args[0])


LHR_OP_NAMES: Dict[str, ClassicalIqoalaOp] = {
    cls.OP_NAME: cls  # type: ignore
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
        subroutines: Dict[str, IqoalaSubroutine],
        meta: ProgramMeta,
        requests: Optional[Dict[str, IqoalaRequest]] = None,
    ) -> None:
        self._instructions: List[ClassicalIqoalaOp] = instructions
        self._subroutines: Dict[str, IqoalaSubroutine] = subroutines
        self._meta: ProgramMeta = meta

        if requests is None:
            self._requests: Dict[str, IqoalaRequest] = {}
        else:
            self._requests: Dict[str, IqoalaRequest] = requests

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
                    # TODO: add duration
                    sigs.append(IqoalaInstructionSignature(typ))
            else:
                sigs.append(IqoalaInstructionSignature(instr.TYP))
        return sigs

    @property
    def subroutines(self) -> Dict[str, IqoalaSubroutine]:
        return self._subroutines

    @subroutines.setter
    def subroutines(self, new_subroutines: Dict[str, IqoalaSubroutine]) -> None:
        self._subroutines = new_subroutines

    @property
    def requests(self) -> Dict[str, IqoalaRequest]:
        return self._requests

    @requests.setter
    def requests(self, new_requests: Dict[str, IqoalaRequest]) -> None:
        self._requests = new_requests

    def __str__(self) -> str:
        # self.me
        # instrs = [
        #     f"{str(i)}\n{self.subroutines[i.arguments[0]]}"  # inline subroutine contents
        #     if isinstance(i, RunSubroutineOp)
        #     else str(i)
        #     for i in self.instructions
        # ]

        # return "\n".join("  " + i for i in instrs)
        return "\n".join("  " + str(i) for i in self.instructions)

    def serialize_meta(self) -> str:
        return self.meta.serialize()

    def serialize_instructions(self) -> str:
        return "\n".join("  " + str(i) for i in self.instructions)

    def serialize_subroutines(self) -> str:
        return "\n".join(s.serialize() for s in self.subroutines.values())

    def serialize(self) -> str:
        return (
            self.meta.serialize()
            + "\n"
            + self.serialize_instructions()
            + "\n"
            + self.serialize_subroutines()
        )


class EndOfTextException(Exception):
    pass


class IqoalaParseError(Exception):
    pass


class IqoalaMetaParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1

    def _read_line(self) -> str:
        while True:
            if self._lineno >= len(self._lines):
                raise EndOfTextException
            line = self._lines[self._lineno]
            self._next_line()
            if len(line) > 0:
                return line
            # if no non-empty line, will always break on EndOfLineException

    def _parse_meta_line(self, key: str, line: str) -> List[str]:
        split = line.split(":")
        assert len(split) >= 1
        assert split[0] == key
        if len(split) == 1:
            return []
        assert len(split) == 2
        if len(split[1]) == 0:
            return []
        values = split[1].split(",")
        return [v.strip() for v in values]

    def _parse_meta_mapping(self, value_str: str) -> Dict[int, str]:
        result_dict = {}
        for v in value_str:
            key_value = [x.strip() for x in v.split("->")]
            assert len(key_value) == 2
            result_dict[int(key_value[0].strip())] = key_value[1].strip()
        return result_dict

    def parse(self) -> ProgramMeta:
        try:
            start_line = self._read_line()
            assert start_line == "META_START"

            name_values = self._parse_meta_line("name", self._read_line())
            assert len(name_values) == 1
            name = name_values[0]

            parameters = self._parse_meta_line("parameters", self._read_line())

            csockets_map = self._parse_meta_line("csockets", self._read_line())
            csockets = self._parse_meta_mapping(csockets_map)
            epr_sockets_map = self._parse_meta_line("epr_sockets", self._read_line())
            epr_sockets = self._parse_meta_mapping(epr_sockets_map)

            end_line = self._read_line()
            if end_line != "META_END":
                raise IqoalaParseError("Could not parse meta.")
        except AssertionError:
            raise IqoalaParseError
        except EndOfTextException:
            raise IqoalaParseError

        return ProgramMeta(name, parameters, csockets, epr_sockets)


class IqoalaInstrParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1

    def _read_line(self) -> str:
        while True:
            if self._lineno >= len(self._lines):
                raise EndOfTextException
            line = self._lines[self._lineno]
            self._next_line()
            if len(line) > 0:
                return line
            # if no non-empty line, will always break on EndOfLineException

    def _parse_var(self, var_str: str) -> Union[str, IqoalaVector]:
        if var_str.startswith("vec<"):
            vec_values_str = var_str[4:-1]
            if len(vec_values_str) == 0:
                vec_values = []
            else:
                vec_values = [x.strip() for x in vec_values_str.split(";")]
            return IqoalaVector(vec_values)
        else:
            return var_str

    def _parse_lhr(self) -> ClassicalIqoalaOp:
        line = self._read_line()

        attr: Optional[IqoalaValue]

        assign_parts = [x.strip() for x in line.split("=")]
        assert len(assign_parts) <= 2
        if len(assign_parts) == 1:
            value = assign_parts[0]
            result = None
        elif len(assign_parts) == 2:
            value = assign_parts[1]
            result = self._parse_var(assign_parts[0])
        value_parts = [x.strip() for x in value.split(":")]
        assert len(value_parts) <= 2
        if len(value_parts) == 2:
            value = value_parts[0]
            attr_str = value_parts[1]
            try:
                attr = int(attr_str)
            except ValueError:
                attr = attr_str
        else:
            value = value_parts[0]
            attr = None

        op_parts = [x.strip() for x in value.split("(")]
        assert len(op_parts) == 2
        op = op_parts[0]
        arguments = op_parts[1].rstrip(")")
        if len(arguments) == 0:
            raw_args = []
        else:
            raw_args = [x.strip() for x in arguments.split(",")]

        args = [self._parse_var(arg) for arg in raw_args]

        # print(f"result = {result}, op = {op}, args = {args}, attr = {attr}")

        lhr_op = LHR_OP_NAMES[op].from_generic_args(result, args, attr)
        return lhr_op

    def parse(self) -> List[ClassicalIqoalaOp]:
        instructions: List[ClassicalIqoalaOp] = []

        try:
            while True:
                instr = self._parse_lhr()
                instructions.append(instr)
        except AssertionError:
            raise IqoalaParseError
        except EndOfTextException:
            pass

        return instructions


class IQoalaSubroutineParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1

    def _read_line(self) -> str:
        while True:
            if self._lineno >= len(self._lines):
                raise EndOfTextException
            line = self._lines[self._lineno]
            self._next_line()
            if len(line) > 0:
                return line
            # if no non-empty line, will always break on EndOfLineException

    def _parse_subrt_meta_line(self, key: str, line: str) -> List[str]:
        split = line.split(":")
        assert len(split) >= 1
        assert split[0] == key
        if len(split) == 1:
            return []
        assert len(split) == 2
        if len(split[1]) == 0:
            return []
        values = split[1].split(",")
        return [v.strip() for v in values]

    def _parse_nqasm_return_mapping(
        self, value_str: str
    ) -> Dict[str, IqoalaSharedMemLoc]:
        result_dict = {}
        for v in value_str:
            key_value = [x.strip() for x in v.split("->")]
            assert len(key_value) == 2
            result_dict[key_value[1]] = IqoalaSharedMemLoc(key_value[0])
        return result_dict

    def _parse_subroutine(self) -> IqoalaSubroutine:
        return_map: Dict[str, IqoalaSharedMemLoc] = {}
        name_line = self._read_line()
        assert name_line.startswith("SUBROUTINE ")
        name = name_line[len("SUBROUTINE") + 1 :]
        params_line = self._parse_subrt_meta_line("params", self._read_line())
        # TODO: use params line?
        return_map_line = self._parse_subrt_meta_line("returns", self._read_line())
        return_map = self._parse_nqasm_return_mapping(return_map_line)
        request_line = self._parse_subrt_meta_line("request", self._read_line())
        assert len(request_line) in [0, 1]
        request_name = None if len(request_line) == 0 else request_line[0]

        start_line = self._read_line()
        assert start_line == "NETQASM_START"
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

        # Check that all templates are declared as params to the subroutine
        if any(arg not in params_line for arg in subrt.arguments):
            raise IqoalaParseError
        return IqoalaSubroutine(name, subrt, return_map, request_name)

    def parse(self) -> Dict[str, IqoalaSubroutine]:
        subroutines: Dict[str, IqoalaSubroutine] = {}
        try:
            while True:
                subrt = self._parse_subroutine()
                subroutines[subrt.name] = subrt
        except EndOfTextException:
            return subroutines


class IQoalaRequestParser:
    def __init__(self, text: str) -> None:
        self._text = text
        lines = [line.strip() for line in text.split("\n")]
        self._lines = [line for line in lines if len(line) > 0]
        self._lineno: int = 0

    def _next_line(self) -> None:
        self._lineno += 1

    def _read_line(self) -> str:
        while True:
            if self._lineno >= len(self._lines):
                raise EndOfTextException
            line = self._lines[self._lineno]
            self._next_line()
            if len(line) > 0:
                return line
            # if no non-empty line, will always break on EndOfLineException

    def _parse_request_line(self, key: str, line: str) -> List[str]:
        split = line.split(":")
        assert len(split) >= 1
        assert split[0] == key
        if len(split) == 1:
            return []
        assert len(split) == 2
        if len(split[1]) == 0:
            return []
        values = split[1].split(",")
        return [v.strip() for v in values]

    def _parse_single_int_value(
        self, key: str, line: str, allow_template: bool = False
    ) -> Union[int, Template]:
        strings = self._parse_request_line(key, line)
        if len(strings) != 1:
            raise IqoalaParseError
        value = strings[0]
        if allow_template:
            if value.startswith("{") and value.endswith("}"):
                value = value.strip("{}").strip()
                return Template(value)
        return int(value)

    def _parse_int_list_value(self, key: str, line: str) -> int:
        strings = self._parse_request_line(key, line)
        return [int(s) for s in strings]

    def _parse_single_float_value(self, key: str, line: str) -> int:
        strings = self._parse_request_line(key, line)
        if len(strings) != 1:
            raise IqoalaParseError
        return float(strings[0])

    def _parse_epr_create_role_value(self, key: str, line: str) -> int:
        strings = self._parse_request_line(key, line)
        if len(strings) != 1:
            raise IqoalaParseError
        try:
            return EprCreateRole[strings[0].upper()]
        except KeyError:
            raise IqoalaParseError

    def _parse_epr_create_type_value(self, key: str, line: str) -> int:
        strings = self._parse_request_line(key, line)
        if len(strings) != 1:
            raise IqoalaParseError
        try:
            return EprCreateType[strings[0].upper()]
        except KeyError:
            raise IqoalaParseError

    def _parse_request(self) -> IqoalaRequest:
        name_line = self._read_line()
        if not name_line.startswith("REQUEST "):
            raise IqoalaParseError
        name = name_line[len("REQUEST") + 1 :]

        role = self._parse_epr_create_role_value("role", self._read_line())
        remote_id = self._parse_single_int_value(
            "remote_id", self._read_line(), allow_template=True
        )
        epr_socket_id = self._parse_single_int_value("epr_socket_id", self._read_line())
        typ = self._parse_epr_create_type_value("typ", self._read_line())
        num_pairs = self._parse_single_int_value("num_pairs", self._read_line())
        fidelity = self._parse_single_float_value("fidelity", self._read_line())
        virt_qubit_ids = self._parse_int_list_value("virt_qubit_ids", self._read_line())
        result_array_addr = self._parse_single_int_value(
            "result_array_addr", self._read_line()
        )

        if role == EprCreateRole.CREATE:
            request = NetstackCreateRequest(
                remote_id=remote_id,
                epr_socket_id=epr_socket_id,
                typ=typ,
                num_pairs=num_pairs,
                fidelity=fidelity,
                virt_qubit_ids=virt_qubit_ids,
                result_array_addr=result_array_addr,
            )
        else:
            assert role == EprCreateRole.RECEIVE
            request = NetstackReceiveRequest(
                remote_id=remote_id,
                epr_socket_id=epr_socket_id,
                typ=typ,
                num_pairs=num_pairs,
                fidelity=fidelity,
                virt_qubit_ids=virt_qubit_ids,
                result_array_addr=result_array_addr,
            )

        return IqoalaRequest(name=name, role=role, request=request)

    def parse(self) -> Dict[str, IqoalaRequest]:
        requests: Dict[str, IqoalaRequest] = {}
        try:
            while True:
                request = self._parse_request()
                requests[request.name] = request
        except EndOfTextException:
            return requests


class IqoalaParser:
    def __init__(
        self,
        text: Optional[str] = None,
        meta_text: Optional[str] = None,
        instr_text: Optional[str] = None,
        subrt_text: Optional[str] = None,
        req_text: Optional[str] = None,
    ) -> None:
        if text is not None:
            meta_text, instr_text, subrt_text, req_text = self._split_text(text)
        else:
            assert meta_text is not None
            assert instr_text is not None
            assert subrt_text is not None
            assert req_text is not None
        self._meta_text = meta_text
        self._instr_text = instr_text
        self._subrt_text = subrt_text
        self._req_text = req_text
        self._meta_parser = IqoalaMetaParser(meta_text)
        self._instr_parser = IqoalaInstrParser(instr_text)
        self._subrt_parser = IQoalaSubroutineParser(subrt_text)
        self._req_parser = IQoalaRequestParser(req_text)

    def _split_text(self, text: str) -> Tuple[str, str, str, str]:
        lines = [line.strip() for line in text.split("\n")]
        meta_end_line: int
        first_subrt_line: int
        first_req_line: Optional[int] = None
        for i, line in enumerate(lines):
            if "META_END" in line:
                meta_end_line = i
                break
        for i, line in enumerate(lines):
            if "SUBROUTINE" in line:
                first_subrt_line = i
                break
        for i, line in enumerate(lines):
            if "REQUEST" in line:
                first_req_line = i
                break

        meta_text = "\n".join(lines[0 : meta_end_line + 1])
        instr_text = "\n".join(lines[meta_end_line + 1 : first_subrt_line])
        if first_req_line is None:
            subrt_text = "\n".join(lines[first_subrt_line:])
            req_text = ""
        else:
            subrt_text = "\n".join(lines[first_subrt_line:first_req_line])
            req_text = "\n".join(lines[first_req_line:])

        return meta_text, instr_text, subrt_text, req_text

    def parse(self) -> IqoalaProgram:
        instructions = self._instr_parser.parse()
        subroutines = self._subrt_parser.parse()
        requests = self._req_parser.parse()
        meta = self._meta_parser.parse()

        # Check that all references to subroutines (in RunSubroutineOp instructions)
        # are valid.
        for instr in instructions:
            if isinstance(instr, RunSubroutineOp):
                subrt_name = instr.subroutine
                if subrt_name not in subroutines:
                    raise IqoalaParseError
        return IqoalaProgram(instructions, subroutines, meta, requests)
