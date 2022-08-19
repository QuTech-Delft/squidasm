from os import times
from typing import Dict

from squidasm.qoala.lang import lhr


class Schedule:
    def __init__(self, timeslot_length: int) -> None:
        self._schedule: Dict[lhr.ClassicalLhrOp, int] = {}

        self._timeslot_length = timeslot_length

    def next_slot(self, now: float) -> int:
        slot = int(now / self._timeslot_length)
        return (slot + 1) * self._timeslot_length
