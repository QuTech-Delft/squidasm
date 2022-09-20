from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from squidasm.qoala.runtime.environment import GlobalEnvironment
from squidasm.qoala.sim.globals import GlobalSimData


@dataclass
class SimulationContext:
    global_env: Optional[GlobalEnvironment] = None
    global_sim_data: Optional[GlobalSimData] = None
