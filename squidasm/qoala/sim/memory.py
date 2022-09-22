from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Union

from netqasm.lang import operand
from netqasm.lang.encoding import RegisterName
from netqasm.sdk.shared_memory import Arrays, RegisterGroup, setup_registers


class RegisterMeta:
    @classmethod
    def prefixes(cls) -> List[str]:
        return ["R", "C", "Q", "M"]

    @classmethod
    def parse(cls, name: str) -> Tuple[RegisterName, int]:
        assert len(name) >= 2
        assert name[0] in cls.prefixes()
        group = RegisterName[name[0]]
        index = int(name[1:])
        assert index < 16
        return group, index


class AppMemory:
    def __init__(self, app_id: int, max_qubits: int) -> None:
        self._app_id: int = app_id
        self._registers: Dict[RegisterName, RegisterGroup] = setup_registers()
        self._arrays: Arrays = Arrays()
        self._virt_qubits: Dict[int, Optional[int]] = {
            i: None for i in range(max_qubits)
        }
        self._prog_counter: int = 0

    @property
    def prog_counter(self) -> int:
        return self._prog_counter

    def increment_prog_counter(self) -> None:
        self._prog_counter += 1

    def set_prog_counter(self, value: int) -> None:
        self._prog_counter = value

    def map_virt_id(self, virt_id: int, phys_id: int) -> None:
        self._virt_qubits[virt_id] = phys_id

    def unmap_virt_id(self, virt_id: int) -> None:
        self._virt_qubits[virt_id] = None

    def unmap_all(self) -> None:
        for virt_id in self._virt_qubits:
            self._virt_qubits[virt_id] = None

    @property
    def qubit_mapping(self) -> Dict[int, Optional[int]]:
        return self._virt_qubits

    def phys_id_for(self, virt_id: int) -> int:
        return self._virt_qubits[virt_id]

    def virt_id_for(self, phys_id: int) -> Optional[int]:
        for virt, phys in self._virt_qubits.items():
            if phys == phys_id:
                return virt
        return None

    def set_reg_value(self, register: Union[str, operand.Register], value: int) -> None:
        if isinstance(register, str):
            name, index = RegisterMeta.parse(register)
        else:
            name, index = register.name, register.index
        self._registers[name][index] = value

    def get_reg_value(self, register: Union[str, operand.Register]) -> int:
        if isinstance(register, str):
            name, index = RegisterMeta.parse(register)
        else:
            name, index = register.name, register.index
        return self._registers[name][index]

    # for compatibility with netqasm Futures
    def get_register(self, register: Union[str, operand.Register]) -> Optional[int]:
        return self.get_reg_value(register)

    # for compatibility with netqasm Futures
    def get_array_part(
        self, address: int, index: Union[int, slice]
    ) -> Union[None, int, List[Optional[int]]]:
        if isinstance(index, int):
            return self.get_array_value(address, index)
        elif isinstance(index, slice):
            return self.get_array_values(address, index.start, index.stop)

    def init_new_array(self, address: int, length: int) -> None:
        self._arrays.init_new_array(address, length)

    def get_array(self, address: int) -> List[Optional[int]]:
        return self._arrays._get_array(address)

    def get_array_entry(self, array_entry: operand.ArrayEntry) -> Optional[int]:
        address, index = self.expand_array_part(array_part=array_entry)
        result = self._arrays[address, index]
        assert (result is None) or isinstance(result, int)
        return result

    def get_array_value(self, addr: int, offset: int) -> Optional[int]:
        address, index = self.expand_array_part(
            array_part=operand.ArrayEntry(operand.Address(addr), offset)
        )
        result = self._arrays[address, index]
        assert (result is None) or isinstance(result, int)
        return result

    def get_array_values(
        self, addr: int, start_offset: int, end_offset
    ) -> List[Optional[int]]:
        values = self.get_array_slice(
            operand.ArraySlice(operand.Address(addr), start_offset, end_offset)
        )
        assert values is not None
        return values

    def set_array_entry(
        self, array_entry: operand.ArrayEntry, value: Optional[int]
    ) -> None:
        address, index = self.expand_array_part(array_part=array_entry)
        self._arrays[address, index] = value

    def set_array_value(self, addr: int, offset: int, value: Optional[int]) -> None:
        address, index = self.expand_array_part(
            array_part=operand.ArrayEntry(operand.Address(addr), offset)
        )
        self._arrays[address, index] = value

    def get_array_slice(
        self, array_slice: operand.ArraySlice
    ) -> Optional[List[Optional[int]]]:
        address, index = self.expand_array_part(array_part=array_slice)
        result = self._arrays[address, index]
        assert (result is None) or isinstance(result, list)
        return result

    def expand_array_part(
        self, array_part: Union[operand.ArrayEntry, operand.ArraySlice]
    ) -> Tuple[int, Union[int, slice]]:
        address: int = array_part.address.address
        index: Union[int, slice]
        if isinstance(array_part, operand.ArrayEntry):
            if isinstance(array_part.index, int):
                index = array_part.index
            else:
                index_from_reg = self.get_reg_value(register=array_part.index)
                if index_from_reg is None:
                    raise RuntimeError(
                        f"Trying to use register {array_part.index} "
                        "to index an array but its value is None"
                    )
                index = index_from_reg
        elif isinstance(array_part, operand.ArraySlice):
            startstop: List[int] = []
            for raw_s in [array_part.start, array_part.stop]:
                if isinstance(raw_s, int):
                    startstop.append(raw_s)
                elif isinstance(raw_s, operand.Register):
                    s = self.get_reg_value(register=raw_s)
                    if s is None:
                        raise RuntimeError(
                            f"Trying to use register {raw_s} to "
                            "index an array but its value is None"
                        )
                    startstop.append(s)
                else:
                    raise RuntimeError(
                        f"Something went wrong: raw_s should be int "
                        f"or Register but is {type(raw_s)}"
                    )
            index = slice(*startstop)
        else:
            raise RuntimeError(
                f"Something went wrong: array_part is a {type(array_part)}"
            )
        return address, index
