from typing import Any, Dict, Generator

from netqasm.lang.parsing.text import parse_text_presubroutine
from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import NVQDeviceConfig, StackConfig, StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

SUBRT = """
# NETQASM 1.0
# APPID 0
array 1 @0
set Q0 0
qalloc Q0
init Q0
x Q0
meas Q0 M0
qfree Q0
store M0 @0[0]
ret_arr @0
"""


class ClientProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={},
            csockets=[],
            epr_sockets=[],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection

        q = Qubit(conn)
        m = q.measure()
        # yield from conn.flush()
        subrt = parse_text_presubroutine(SUBRT)
        yield from conn.commit_subroutine(subrt)

        return {"m": int(m)}


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

    num_times = 1
    client = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    cfg = StackNetworkConfig(stacks=[client], links=[])

    num_pairs = 10

    results = run(cfg, {"client": ClientProgram()}, num_times)
    print(results)
