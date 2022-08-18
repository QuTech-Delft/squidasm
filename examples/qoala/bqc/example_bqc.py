import os

import netsquid as ns

from squidasm.qoala.lang import lhr as lp
from squidasm.qoala.runtime.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramMeta


def test_run_two_nodes_epr():
    program_client_file = os.path.join(os.path.dirname(__file__), "bqc_5_6_client.lhr")
    with open(program_client_file) as file:
        program_client_text = file.read()
    program_client = lp.LhrParser(program_client_text).parse()
    program_client.meta = ProgramMeta(
        name="client",
        parameters={"theta_discrete": None},
        csockets=["server"],
        epr_sockets=["server"],
        max_qubits=1,
    )
    client_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )

    program_server_file = os.path.join(os.path.dirname(__file__), "bqc_5_6_server.lhr")
    with open(program_server_file) as file:
        program_server_text = file.read()
    program_server = lp.LhrParser(program_server_text).parse()
    program_server.meta = ProgramMeta(
        name="server",
        parameters={},
        csockets=["client"],
        epr_sockets=["client"],
        max_qubits=2,
    )
    server_stack = StackConfig(
        name="server",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    prog_server_instance = ProgramInstance(program_server, {}, 1, 0.0)
    prog_client_instance = ProgramInstance(
        program_client, {"alpha": 8, "beta": 8, "theta1": 0, "theta2": 0}, 1, 0.0
    )

    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])
    for i in range(1):
        result = run(
            cfg,
            programs={"client": prog_client_instance, "server": prog_server_instance},
        )
        print(result)
        ns.sim_reset()


if __name__ == "__main__":
    # LogManager.set_log_level("INFO")
    # LogManager.log_to_file(os.path.join(os.path.dirname(__file__), "debug.log"))
    test_run_two_nodes_epr()
