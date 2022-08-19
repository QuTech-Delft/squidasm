import os
from calendar import c
from dataclasses import dataclass
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


@dataclass
class BqcParty:
    name: str
    node_id: int


def load_client_program(client_name: str, server_name: str) -> lp.LhrProgram:
    program_client_file = os.path.join(os.path.dirname(__file__), "bqc_5_6_client.lhr")
    with open(program_client_file) as file:
        program_client_text = file.read()
    program_client = lp.LhrParser(program_client_text).parse()
    program_client.meta = ProgramMeta(
        name=client_name,
        parameters={"theta_discrete": None},
        csockets=[server_name],
        epr_sockets=[server_name],
        max_qubits=1,
    )

    return program_client


def load_server_program(client_name: str, server_name: str) -> lp.LhrProgram:
    program_server_file = os.path.join(os.path.dirname(__file__), "bqc_5_6_server.lhr")
    with open(program_server_file) as file:
        program_server_text = file.read()
    program_server = lp.LhrParser(program_server_text).parse()
    program_server.meta = ProgramMeta(
        name=server_name,
        parameters={},
        csockets=[client_name],
        epr_sockets=[client_name],
        max_qubits=2,
    )

    return program_server


def create_client_instance(client: BqcParty, server: BqcParty) -> ProgramInstance:
    program_client = load_client_program(client.name, server.name)

    return ProgramInstance(
        program_client,
        {"alpha": 8, "beta": 8, "theta1": 0, "theta2": 0, "server_id": server.node_id},
        1,
        0.0,
    )


def create_server_instance(client: BqcParty, server: BqcParty) -> ProgramInstance:
    program_server = load_server_program(client.name, server.name)

    return ProgramInstance(
        program_server,
        {"client_id": client.node_id},
        1,
        0.0,
    )


def create_stack_config(party: BqcParty) -> StackConfig:
    return StackConfig(
        name=party.name,
        node_id=party.node_id,
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )


def run_bqc():
    server = BqcParty("server", 0)
    client1 = BqcParty("client1", 1)
    client2 = BqcParty("client2", 2)

    client1_stack = create_stack_config(client1)
    client2_stack = create_stack_config(client2)
    server_stack = create_stack_config(server)
    link1 = LinkConfig(stack1=client1.name, stack2=server.name, typ="perfect")
    link2 = LinkConfig(stack1=client2.name, stack2=server.name, typ="perfect")

    client1_program = create_client_instance(client1, server)
    client2_program = create_client_instance(client2, server)
    server_program1 = create_server_instance(client1, server)
    server_program2 = create_server_instance(client2, server)

    cfg = StackNetworkConfig(
        stacks=[client1_stack, client2_stack, server_stack], links=[link1, link2]
    )

    server_schedule = Schedule(timeslot_length=1337)

    for i in range(1):
        result = run(
            cfg,
            programs={
                client1.name: [client1_program],
                client2.name: [client2_program],
                server.name: [server_program1, server_program2],
            },
            schedules={server.name: server_schedule},
        )
        print(result)
        ns.sim_reset()


if __name__ == "__main__":
    LogManager.set_log_level("DEBUG")
    LogManager.log_to_file(os.path.join(os.path.dirname(__file__), "debug.log"))
    run_bqc()
