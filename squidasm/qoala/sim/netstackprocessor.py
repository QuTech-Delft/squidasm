import logging
from tkinter import W
from typing import Optional

from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory
from squidasm.qoala.sim.netstackinterface import NetstackInterface


class NetstackProcessor:
    def __init__(self, interface: NetstackInterface) -> None:
        self._interface = interface

        self._name = f"{interface.name}_NetstackProcessor"

        self._logger: logging.Logger = LogManager.get_stack_logger(
            f"{self.__class__.__name__}({self._name})"
        )

        # memory of current program, only not-None when processor is active
        self._current_prog_mem: Optional[ProgramMemory] = None
