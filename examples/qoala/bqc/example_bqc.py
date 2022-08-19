import os
from calendar import c
from typing import Dict

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
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramMeta


def load_client_program() -> lp.LhrProgram:
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

    return program_client


def load_server_program() -> lp.LhrProgram:
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

    return program_server


def create_client_instance(server_id: int) -> ProgramInstance:
    program_client = load_client_program()

    return ProgramInstance(
        program_client,
        {"alpha": 8, "beta": 8, "theta1": 0, "theta2": 0, "server_id": server_id},
        1,
        0.0,
    )


def create_server_instance(client_id: int) -> ProgramInstance:
    program_server = load_server_program()

    return ProgramInstance(
        program_server,
        {"client_id": client_id},
        1,
        0.0,
    )


def create_stack_config(name: str, node_id: int) -> StackConfig:
    return StackConfig(
        name=name,
        node_id=node_id,
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )


def run_bqc():
    server_id = 0
    client_id = 1

    client_stack = create_stack_config("client", client_id)
    server_stack = create_stack_config("server", server_id)
    link = LinkConfig(stack1="client", stack2="server", typ="perfect")

    client_program = create_client_instance(server_id=server_id)
    server_program = create_server_instance(client_id=client_id)

    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])

    server_schedule = Schedule(timeslot_length=1337)

    for i in range(1):
        result = run(
            cfg,
            programs={"client": client_program, "server": server_program},
            schedules={"server": server_schedule},
        )
        print(result)
        ns.sim_reset()


if __name__ == "__main__":
    LogManager.set_log_level("DEBUG")
    LogManager.log_to_file(os.path.join(os.path.dirname(__file__), "debug.log"))
    run_bqc()
