from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple, Type

import netsquid as ns
from netqasm.lang.instr.core import CreateEPRInstruction, RecvEPRInstruction
from netsquid.components import QuantumProcessor
from netsquid.nodes import Node
from netsquid.qubits import ketstates, operators, qubitapi
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor

from pydynaa import EventExpression
from squidasm.qoala.lang.iqoala import IqoalaParser, IqoalaProgram
from squidasm.qoala.runtime.config import GenericQDeviceConfig
from squidasm.qoala.runtime.environment import GlobalEnvironment, GlobalNodeInfo
from squidasm.qoala.runtime.program import (
    BatchInfo,
    ProgramInput,
    ProgramInstance,
    ProgramResult,
)
from squidasm.qoala.runtime.schedule import (
    ProgramTask,
    ProgramTaskList,
    Schedule,
    ScheduleEntry,
    ScheduleTime,
    TaskBuilder,
)
from squidasm.qoala.sim.build import build_generic_qprocessor
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, Topology, UnitModule
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnode import ProcNode
from squidasm.util.tests import has_multi_state, has_state, netsquid_run, yield_from


def create_global_env(
    num_qubits: int, names: List[str] = ["alice", "bob", "charlie"]
) -> GlobalEnvironment:

    env = GlobalEnvironment()
    for i, name in enumerate(names):
        env.add_node(i, GlobalNodeInfo.default_nv(name, i, num_qubits))
    return env


def create_egp_protocols(node1: Node, node2: Node) -> Tuple[EgpProtocol, EgpProtocol]:
    link_dist = PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=1000.0)
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[node1, node2],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    return EgpProtocol(node1, link_prot), EgpProtocol(node2, link_prot)


def create_server_tasks(server_program: IqoalaProgram) -> ProgramTaskList:
    tasks = []

    cl_dur = 1e3
    cc_dur = 10e6
    ql_dur = 1e3
    qc_dur = 1e6

    tasks.append(TaskBuilder.CL(cl_dur, 0))
    tasks.append(TaskBuilder.CL(cl_dur, 1))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_0"))
    tasks.append(TaskBuilder.CL(cl_dur, 2))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_1"))
    tasks.append(TaskBuilder.CL(cl_dur, 3))
    tasks.append(TaskBuilder.QL(ql_dur, "local_cphase", 0))
    tasks.append(TaskBuilder.QL(ql_dur, "local_cphase", 1))
    tasks.append(TaskBuilder.QL(ql_dur, "local_cphase", 2))
    tasks.append(TaskBuilder.CC(cc_dur, 4))
    tasks.append(TaskBuilder.CL(cl_dur, 5))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 0))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 1))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 2))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 3))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 4))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_1", 5))
    tasks.append(TaskBuilder.CC(cc_dur, 6))
    tasks.append(TaskBuilder.CC(cc_dur, 7))
    tasks.append(TaskBuilder.CL(cl_dur, 8))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 0))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 1))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 2))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 3))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 4))
    tasks.append(TaskBuilder.QL(ql_dur, "meas_qubit_0", 5))
    tasks.append(TaskBuilder.CL(cl_dur, 9))
    tasks.append(TaskBuilder.CL(cl_dur, 10))

    return ProgramTaskList(server_program, {i: task for i, task in enumerate(tasks)})


def create_client_tasks(client_program: IqoalaProgram) -> ProgramTaskList:
    tasks = []

    cl_dur = 1e3
    cc_dur = 10e6
    ql_dur = 1e3
    qc_dur = 1e6

    tasks.append(TaskBuilder.CL(cl_dur, 0))
    tasks.append(TaskBuilder.CL(cl_dur, 1))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_0"))
    tasks.append(TaskBuilder.CL(cl_dur, 2))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 0))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 1))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 2))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 3))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 4))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_0", 5))

    tasks.append(TaskBuilder.CL(cl_dur, 3))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_1"))
    tasks.append(TaskBuilder.CL(cl_dur, 4))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 0))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 1))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 2))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 3))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 4))
    tasks.append(TaskBuilder.QL(ql_dur, "post_epr_1", 5))

    tasks.append(TaskBuilder.CL(cl_dur, 5))
    tasks.append(TaskBuilder.CL(cl_dur, 6))
    tasks.append(TaskBuilder.CL(cl_dur, 7))
    tasks.append(TaskBuilder.CL(cl_dur, 8))
    tasks.append(TaskBuilder.CC(cc_dur, 9))
    tasks.append(TaskBuilder.CC(cc_dur, 10))
    tasks.append(TaskBuilder.CL(cl_dur, 11))
    tasks.append(TaskBuilder.CL(cl_dur, 12))
    tasks.append(TaskBuilder.CL(cl_dur, 13))
    tasks.append(TaskBuilder.CL(cl_dur, 14))
    tasks.append(TaskBuilder.CL(cl_dur, 15))
    tasks.append(TaskBuilder.CC(cc_dur, 16))
    tasks.append(TaskBuilder.CL(cl_dur, 17))
    tasks.append(TaskBuilder.CL(cl_dur, 18))

    return ProgramTaskList(client_program, {i: task for i, task in enumerate(tasks)})


def create_server_schedule(num_tasks: int) -> Schedule:
    entries = [
        (ScheduleTime(int(i * 1e8)), ScheduleEntry(pid=0, task_index=i))
        for i in range(num_tasks)
    ]
    return Schedule(entries)


def create_client_schedule(num_tasks: int) -> Schedule:
    entries = [
        (ScheduleTime(None), ScheduleEntry(pid=0, task_index=i))
        for i in range(num_tasks)
    ]
    return Schedule(entries)


@dataclass
class BqcResult:
    client_process: IqoalaProcess
    server_process: IqoalaProcess
    client_procnode: ProcNode
    server_procnode: ProcNode


def run_bqc(
    alpha,
    beta,
    theta1,
    theta2,
):
    num_qubits = 3
    unit_module = UnitModule.default_generic(num_qubits)
    global_env = create_global_env(num_qubits, names=["client", "server"])
    server_id = global_env.get_node_id("server")
    client_id = global_env.get_node_id("client")

    path = os.path.join(os.path.dirname(__file__), "bqc_server.iqoala")
    with open(path) as file:
        server_text = file.read()
    server_program = IqoalaParser(server_text).parse()
    server_tasks = create_server_tasks(server_program)

    server_cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    server_qprocessor = build_generic_qprocessor(
        name="server_qprocessor", cfg=server_cfg
    )

    server_procnode = ProcNode(
        "server", global_env, server_qprocessor, node_id=server_id
    )

    server_batch_info = BatchInfo(
        program=server_program,
        inputs=[ProgramInput({"client_id": client_id})],
        num_iterations=1,
        deadline=0,
        tasks=server_tasks,
        num_qubits=3,
    )
    server_procnode.submit_batch(server_batch_info)
    server_procnode.initialize_runtime()

    server_schedule = create_server_schedule(len(server_tasks.tasks))
    server_procnode.install_schedule(server_schedule)

    # path = os.path.join(os.path.dirname(__file__), "bqc_client.iqoala")
    # with open(path) as file:
    #     client_text = file.read()
    # client_program = IqoalaParser(client_text).parse()
    # client_tasks = create_client_tasks(client_program)

    # client_procnode = create_procnode("client", global_env, num_qubits)
    # client_process = create_process(
    #     pid=0,
    #     program=client_program,
    #     unit_module=unit_module,
    #     host_interface=client_procnode.host._interface,
    #     inputs={
    #         "server_id": server_id,
    #         "alpha": alpha,
    #         "beta": beta,
    #         "theta1": theta1,
    #         "theta2": theta2,
    #     },
    #     tasks=client_tasks,
    # )
    # client_procnode.add_process(client_process)
    # client_procnode.scheduler.initialize(client_process)

    # client_schedule = create_client_schedule(len(client_tasks.tasks))
    # client_procnode.install_schedule(client_schedule)

    # client_egp, server_egp = create_egp_protocols(
    #     client_procnode.node, server_procnode.node
    # )
    # client_procnode.egpmgr.add_egp(server_id, client_egp)
    # server_procnode.egpmgr.add_egp(client_id, server_egp)

    # client_procnode.connect_to(server_procnode)

    # server_procnode.start()
    # client_procnode.start()
    # ns.sim_run()

    # return BqcResult(
    #     client_process=client_process,
    #     server_process=server_process,
    #     client_procnode=client_procnode,
    #     server_procnode=server_procnode,
    # )


def expected_rsp_qubit(theta: int, p: int, dummy: bool):
    expected = qubitapi.create_qubits(1)[0]

    if dummy:
        if p == 0:
            qubitapi.assign_qstate(expected, ketstates.s0)
        elif p == 1:
            qubitapi.assign_qstate(expected, ketstates.s1)
    else:
        if (theta, p) == (0, 0):
            qubitapi.assign_qstate(expected, ketstates.h0)
        elif (theta, p) == (0, 1):
            qubitapi.assign_qstate(expected, ketstates.h1)
        if (theta, p) == (8, 0):
            qubitapi.assign_qstate(expected, ketstates.y0)
        elif (theta, p) == (8, 1):
            qubitapi.assign_qstate(expected, ketstates.y1)
        if (theta, p) == (16, 0):
            qubitapi.assign_qstate(expected, ketstates.h1)
        elif (theta, p) == (16, 1):
            qubitapi.assign_qstate(expected, ketstates.h0)
        if (theta, p) == (-8, 0):
            qubitapi.assign_qstate(expected, ketstates.y1)
        elif (theta, p) == (-8, 1):
            qubitapi.assign_qstate(expected, ketstates.y0)

    return expected


def expected_rsp_state(theta: int, p: int, dummy: bool):
    expected = qubitapi.create_qubits(1)[0]

    if dummy:
        if p == 0:
            return ketstates.s0
        elif p == 1:
            return ketstates.s1
    else:
        if (theta, p) == (0, 0):
            return ketstates.h0
        elif (theta, p) == (0, 1):
            return ketstates.h1
        if (theta, p) == (8, 0):
            return ketstates.y0
        elif (theta, p) == (8, 1):
            return ketstates.y1
        if (theta, p) == (16, 0):
            return ketstates.h1
        elif (theta, p) == (16, 1):
            return ketstates.h0
        if (theta, p) == (-8, 0):
            return ketstates.y1
        elif (theta, p) == (-8, 1):
            return ketstates.y0

    return expected.qstate


def test_bqc():

    # Effective computation: measure in Z the following state:
    # H Rz(beta) H Rz(alpha) |+>
    # m2 should be this outcome

    # angles are in multiples of pi/16

    def check(alpha, beta, theta1, theta2, expected):
        ns.sim_reset()
        results = [
            run_bqc(
                alpha=alpha,
                beta=beta,
                theta1=theta1,
                theta2=theta2,
            )
            for _ in range(1)
        ]
        m2s = [result.server_process.result.values["m2"] for result in results]
        assert all(m2 == expected for m2 in m2s)

    check(alpha=8, beta=8, theta1=0, theta2=0, expected=0)
    check(alpha=8, beta=24, theta1=0, theta2=0, expected=1)
    check(alpha=8, beta=8, theta1=13, theta2=27, expected=0)
    check(alpha=8, beta=24, theta1=2, theta2=22, expected=1)


if __name__ == "__main__":
    # test_bqc_1()
    # test_bqc_2()
    test_bqc()
