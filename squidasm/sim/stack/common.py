import logging
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Set, Tuple, Union

import netsquid as ns
from netqasm.lang import operand
from netqasm.lang.encoding import RegisterName
from netqasm.sdk.shared_memory import Arrays, RegisterGroup, setup_registers
from netsquid.components.component import Component, Port
from netsquid.protocols import Protocol

from pydynaa import EventExpression


class SimTimeFilter(logging.Filter):
    def filter(self, record):
        record.simtime = ns.sim_time()
        return True


class LogManager:
    STACK_LOGGER = "Stack"
    _LOGGER_HAS_BEEN_SETUP = False

    @classmethod
    def _setup_stack_logger(cls) -> None:
        logger = logging.getLogger(cls.STACK_LOGGER)
        formatter = logging.Formatter(
            "%(levelname)s:%(simtime)s ns:%(name)s:%(message)s"
        )
        syslog = logging.StreamHandler()
        syslog.setFormatter(formatter)
        syslog.addFilter(SimTimeFilter())
        logger.addHandler(syslog)
        logger.propagate = False
        cls._LOGGER_HAS_BEEN_SETUP = True

    @classmethod
    def get_stack_logger(cls, sub_logger: Optional[str] = None) -> logging.Logger:
        if not cls._LOGGER_HAS_BEEN_SETUP:
            cls._setup_stack_logger()
        logger = logging.getLogger(cls.STACK_LOGGER)
        if sub_logger is None:
            return logger
        else:
            return logger.getChild(sub_logger)

    @classmethod
    def set_log_level(cls, level: Union[int, str]) -> None:
        logger = cls.get_stack_logger()
        logger.setLevel(level)

    @classmethod
    def get_log_level(cls) -> int:
        return cls.get_stack_logger().level

    @classmethod
    def log_to_file(cls, path: str) -> None:
        fileHandler = logging.FileHandler(path, mode="w")
        formatter = logging.Formatter(
            "%(levelname)s:%(simtime)s ns:%(name)s:%(message)s"
        )
        fileHandler.setFormatter(formatter)
        fileHandler.addFilter(SimTimeFilter())
        cls.get_stack_logger().addHandler(fileHandler)


class PortListener(Protocol):
    def __init__(self, port: Port, signal_label: str) -> None:
        self._buffer: List[bytes] = []
        self._port: Port = port
        self._signal_label = signal_label
        self.add_signal(signal_label)

    @property
    def buffer(self) -> List[bytes]:
        return self._buffer

    def run(self) -> Generator[EventExpression, None, None]:
        while True:
            # wait for an event saying that there is new input
            yield self.await_port_input(self._port)

            counter = 0
            # read all inputs and count them
            while True:
                input = self._port.rx_input()
                if input is None:
                    break
                self._buffer += input.items
                counter += 1
            # if there are n inputs, there have been n events, but we yielded only
            # on one of them so far. "Flush" these n-1 additional events:
            while counter > 1:
                yield self.await_port_input(self._port)
                counter -= 1

            # only after having yielded on all current events, we can schedule a
            # notification event, so that its reactor can handle all inputs at once
            self.send_signal(self._signal_label)


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


class ComponentProtocol(Protocol):
    def __init__(self, name: str, comp: Component) -> None:
        super().__init__(name)
        self._listeners: Dict[str, PortListener] = {}
        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({comp.name})"
        )

    def add_listener(self, name, listener: PortListener) -> None:
        self._listeners[name] = listener

    def _receive_msg(
        self, listener_name: str, wake_up_signal: str
    ) -> Generator[EventExpression, None, str]:
        listener = self._listeners[listener_name]
        if len(listener.buffer) == 0:
            yield self.await_signal(sender=listener, signal_label=wake_up_signal)
        return listener.buffer.pop(0)

    def start(self) -> None:
        super().start()
        for listener in self._listeners.values():
            listener.start()

    def stop(self) -> None:
        for listener in self._listeners.values():
            listener.stop()
        super().stop()


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


@dataclass
class NetstackCreateRequest:
    app_id: int
    remote_node_id: int
    epr_socket_id: int
    qubit_array_addr: int
    arg_array_addr: int
    result_array_addr: int


@dataclass
class NetstackReceiveRequest:
    app_id: int
    remote_node_id: int
    epr_socket_id: int
    qubit_array_addr: int
    result_array_addr: int


@dataclass
class NetstackBreakpointCreateRequest:
    app_id: int


@dataclass
class NetstackBreakpointReceiveRequest:
    app_id: int


class AllocError(Exception):
    pass


class PhysicalQuantumMemory:
    def __init__(self, qubit_count: int) -> None:
        self._qubit_count = qubit_count
        self._allocated_ids: Set[int] = set()
        self._comm_qubit_ids: Set[int] = {i for i in range(qubit_count)}

    @property
    def qubit_count(self) -> int:
        return self._qubit_count

    @property
    def comm_qubit_count(self) -> int:
        return len(self._comm_qubit_ids)

    def allocate(self) -> int:
        for i in range(self._qubit_count):
            if i not in self._allocated_ids:
                self._allocated_ids.add(i)
                return i
        raise AllocError("No more qubits available")

    def allocate_comm(self) -> int:
        for i in range(self._qubit_count):
            if i not in self._allocated_ids and i in self._comm_qubit_ids:
                self._allocated_ids.add(i)
                return i
        raise AllocError("No more comm qubits available")

    def free(self, id: int) -> None:
        self._allocated_ids.remove(id)

    def is_allocated(self, id: int) -> bool:
        return id in self._allocated_ids

    def clear(self) -> None:
        self._allocated_ids = {}


class NVPhysicalQuantumMemory(PhysicalQuantumMemory):
    def __init__(self, qubit_count: int) -> None:
        super().__init__(qubit_count)
        self._comm_qubit_ids: Set[int] = {0}
