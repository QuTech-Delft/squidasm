from typing import Dict

from squidasm.qoala.lang import iqoala


class Schedule:
    def __init__(self, timeslot_length: int) -> None:
        self._schedule: Dict[iqoala.ClassicalIqoalaOp, int] = {}

        self._timeslot_length = timeslot_length

    def next_slot(self, now: float) -> int:
        slot = int(now / self._timeslot_length)
        return (slot + 1) * self._timeslot_length
