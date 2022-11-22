from __future__ import annotations

import math
import os
from ast import Not
from dataclasses import dataclass
from http import server
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
from squidasm.qoala.runtime.config import (
    GenericQDeviceConfig,
    LinkConfig,
    ProcNodeConfig,
    ProcNodeNetworkConfig,
)
from squidasm.qoala.runtime.environment import GlobalEnvironment, GlobalNodeInfo
from squidasm.qoala.runtime.program import (
    BatchInfo,
    BatchResult,
    ProgramInput,
    ProgramInstance,
    ProgramResult,
)
from squidasm.qoala.runtime.schedule import (
    ProgramTask,
    ProgramTaskList,
    Schedule,
    ScheduleEntry,
    SchedulerInput,
    SchedulerOutput,
    SchedulerOutputEntry,
    ScheduleSolver,
    ScheduleTime,
    TaskBuilder,
)
from squidasm.qoala.sim.build import (
    build_generic_qprocessor,
    build_ll_protocol,
    build_network,
    build_procnode,
)
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.logging import LogManager
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, Topology, UnitModule
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnode import ProcNode
from squidasm.qoala.sim.procnodecomp import ProcNodeComponent
from squidasm.util.tests import has_multi_state, has_state, netsquid_run, yield_from


def create_global_env(
    num_qubits: int, names: List[str] = ["alice", "bob", "charlie"]
) -> GlobalEnvironment:

    env = GlobalEnvironment()
    for i, name in enumerate(names):
        env.add_node(i, GlobalNodeInfo.default_nv(name, i, num_qubits))
    return env


def create_egp_protocols(node1: Node, node2: Node) -> Tuple[EgpProtocol, EgpProtocol]:
    link_dist = PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=0)
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[node1, node2],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    return EgpProtocol(node1, link_prot), EgpProtocol(node2, link_prot)


def create_server_tasks(
    server_program: IqoalaProgram, cfg: ProcNodeConfig
) -> ProgramTaskList:
    tasks = []

    cl_dur = 1e3
    cc_dur = 10e6
    ql_dur = 1e4
    qc_dur = 1e6

    qdevice_cfg: GenericQDeviceConfig = cfg.qdevice_cfg

    set_dur = cfg.instr_latency
    rot_dur = qdevice_cfg.single_qubit_gate_time
    h_dur = qdevice_cfg.single_qubit_gate_time
    meas_dur = qdevice_cfg.measure_time
    free_dur = cfg.instr_latency
    cphase_dur = qdevice_cfg.two_qubit_gate_time

    # csocket = assign_cval() : 0
    tasks.append(TaskBuilder.CL(cl_dur, 0))
    # run_subroutine(vec<client_id>) : create_epr_0
    tasks.append(TaskBuilder.CL(cl_dur, 1))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_0"))
    # run_subroutine(vec<client_id>) : create_epr_1
    tasks.append(TaskBuilder.CL(cl_dur, 2))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_1"))
    # run_subroutine(vec<client_id>) : local_cphase
    tasks.append(TaskBuilder.CL(cl_dur, 3))
    tasks.append(TaskBuilder.QL(set_dur, "local_cphase", 0))
    tasks.append(TaskBuilder.QL(set_dur, "local_cphase", 1))
    tasks.append(TaskBuilder.QL(cphase_dur, "local_cphase", 2))
    # delta1 = recv_cmsg(client_id)
    tasks.append(TaskBuilder.CC(cc_dur, 4))
    # vec<m1> = run_subroutine(vec<delta1>) : meas_qubit_1
    tasks.append(TaskBuilder.CL(cl_dur, 5))
    tasks.append(TaskBuilder.QL(set_dur, "meas_qubit_1", 0))
    tasks.append(TaskBuilder.QL(rot_dur, "meas_qubit_1", 1))
    tasks.append(TaskBuilder.QL(h_dur, "meas_qubit_1", 2))
    tasks.append(TaskBuilder.QL(meas_dur, "meas_qubit_1", 3))
    tasks.append(TaskBuilder.QL(free_dur, "meas_qubit_1", 4))
    # send_cmsg(csocket, m1)
    tasks.append(TaskBuilder.CC(cc_dur, 6))
    # delta2 = recv_cmsg(csocket)
    tasks.append(TaskBuilder.CC(cc_dur, 7))
    # vec<m2> = run_subroutine(vec<delta2>) : meas_qubit_0
    tasks.append(TaskBuilder.CL(cl_dur, 8))
    tasks.append(TaskBuilder.QL(set_dur, "meas_qubit_0", 0))
    tasks.append(TaskBuilder.QL(rot_dur, "meas_qubit_0", 1))
    tasks.append(TaskBuilder.QL(h_dur, "meas_qubit_0", 2))
    tasks.append(TaskBuilder.QL(meas_dur, "meas_qubit_0", 3))
    tasks.append(TaskBuilder.QL(free_dur, "meas_qubit_0", 4))
    # return_result(m1)
    tasks.append(TaskBuilder.CL(cl_dur, 9))
    # return_result(m2)
    tasks.append(TaskBuilder.CL(cl_dur, 10))

    return ProgramTaskList(server_program, {i: task for i, task in enumerate(tasks)})


def create_client_tasks(
    client_program: IqoalaProgram, cfg: ProcNodeConfig
) -> ProgramTaskList:
    tasks = []

    cl_dur = 1e3
    cc_dur = 10e6
    ql_dur = 1e3
    qc_dur = 1e6

    qdevice_cfg: GenericQDeviceConfig = cfg.qdevice_cfg

    set_dur = cfg.instr_latency
    rot_dur = qdevice_cfg.single_qubit_gate_time
    h_dur = qdevice_cfg.single_qubit_gate_time
    meas_dur = qdevice_cfg.measure_time
    free_dur = cfg.instr_latency
    cphase_dur = qdevice_cfg.two_qubit_gate_time

    tasks.append(TaskBuilder.CL(cl_dur, 0))
    tasks.append(TaskBuilder.CL(cl_dur, 1))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_0"))
    tasks.append(TaskBuilder.CL(cl_dur, 2))
    tasks.append(TaskBuilder.QL(set_dur, "post_epr_0", 0))
    tasks.append(TaskBuilder.QL(rot_dur, "post_epr_0", 1))
    tasks.append(TaskBuilder.QL(h_dur, "post_epr_0", 2))
    tasks.append(TaskBuilder.QL(meas_dur, "post_epr_0", 3))
    tasks.append(TaskBuilder.QL(free_dur, "post_epr_0", 4))

    tasks.append(TaskBuilder.CL(cl_dur, 3))
    tasks.append(TaskBuilder.QC(qc_dur, "create_epr_1"))
    tasks.append(TaskBuilder.CL(cl_dur, 4))
    tasks.append(TaskBuilder.QL(set_dur, "post_epr_1", 0))
    tasks.append(TaskBuilder.QL(rot_dur, "post_epr_1", 1))
    tasks.append(TaskBuilder.QL(h_dur, "post_epr_1", 2))
    tasks.append(TaskBuilder.QL(meas_dur, "post_epr_1", 3))
    tasks.append(TaskBuilder.QL(free_dur, "post_epr_1", 4))

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


class NaiveSolver(ScheduleSolver):
    @classmethod
    def solve(cls, input: SchedulerInput) -> SchedulerOutput:
        output_entries: List[SchedulerOutputEntry] = []

        assert len(input.num_executions) == input.num_programs
        assert len(input.num_instructions) == input.num_programs
        assert len(input.instr_durations) == input.num_programs

        current_time = 0

        for i in range(input.num_programs):
            num_executions = input.num_executions[i]
            num_instructions = input.num_instructions[i]
            instr_durations = input.instr_durations[i]
            for j in range(num_executions):
                for k in range(num_instructions):
                    duration = instr_durations[k]
                    entry = SchedulerOutputEntry(
                        app_index=i,
                        ex_index=j,
                        instr_index=k,
                        start_time=current_time,
                        end_time=current_time + duration,
                    )
                    current_time += duration
                    output_entries.append(entry)

        return SchedulerOutput(output_entries)


class NoTimeSolver(ScheduleSolver):
    @classmethod
    def solve(cls, input: SchedulerInput) -> SchedulerOutput:
        output_entries: List[SchedulerOutputEntry] = []

        assert len(input.num_executions) == input.num_programs
        assert len(input.num_instructions) == input.num_programs
        assert len(input.instr_durations) == input.num_programs

        current_time = 0

        for i in range(input.num_programs):
            num_executions = input.num_executions[i]
            num_instructions = input.num_instructions[i]
            instr_durations = input.instr_durations[i]
            for j in range(num_executions):
                for k in range(num_instructions):
                    duration = instr_durations[k]
                    entry = SchedulerOutputEntry(
                        app_index=i,
                        ex_index=j,
                        instr_index=k,
                        start_time=None,
                        end_time=current_time + duration,
                    )
                    current_time += duration
                    output_entries.append(entry)

        return SchedulerOutput(output_entries)


@dataclass
class BqcResult:
    client_results: Dict[int, BatchResult]
    server_results: Dict[int, BatchResult]


def run_bqc(alpha, beta, theta1, theta2, num_iterations: int):
    num_qubits = 3
    global_env = create_global_env(num_qubits, names=["client", "server"])
    server_id = global_env.get_node_id("server")
    client_id = global_env.get_node_id("client")

    server_node_cfg = ProcNodeConfig(
        name="server",
        node_id=server_id,
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(num_qubits),
        instr_latency=1000,
    )
    client_node_cfg = ProcNodeConfig(
        name="client",
        node_id=client_id,
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(num_qubits),
        instr_latency=1000,
    )
    link_cfg = LinkConfig.perfect_config("server", "client")

    network_cfg = ProcNodeNetworkConfig(
        nodes=[server_node_cfg, client_node_cfg], links=[link_cfg]
    )
    network = build_network(network_cfg, global_env)
    server_procnode = network.nodes["server"]
    client_procnode = network.nodes["client"]

    path = os.path.join(os.path.dirname(__file__), "bqc_server.iqoala")
    with open(path) as file:
        server_text = file.read()
    server_program = IqoalaParser(server_text).parse()
    server_tasks = create_server_tasks(server_program, server_node_cfg)
    server_inputs = [
        ProgramInput({"client_id": client_id}) for _ in range(num_iterations)
    ]
    server_batch_info = BatchInfo(
        program=server_program,
        inputs=server_inputs,
        num_iterations=num_iterations,
        deadline=0,
        tasks=server_tasks,
        num_qubits=3,
    )
    server_procnode.submit_batch(server_batch_info)
    server_procnode.initialize_runtime()
    # server_procnode.scheduler.solve_and_install_schedule(NaiveSolver)
    server_procnode.scheduler.solve_and_install_schedule(NoTimeSolver)

    path = os.path.join(os.path.dirname(__file__), "bqc_client.iqoala")
    with open(path) as file:
        client_text = file.read()
    client_program = IqoalaParser(client_text).parse()
    client_tasks = create_client_tasks(client_program, client_node_cfg)
    client_inputs = [
        ProgramInput(
            {
                "server_id": server_id,
                "alpha": alpha,
                "beta": beta,
                "theta1": theta1,
                "theta2": theta2,
            }
        )
        for _ in range(num_iterations)
    ]

    client_batch_info = BatchInfo(
        program=client_program,
        inputs=client_inputs,
        num_iterations=num_iterations,
        deadline=0,
        tasks=client_tasks,
        num_qubits=3,
    )
    client_procnode.submit_batch(client_batch_info)
    client_procnode.initialize_runtime()
    # client_procnode.scheduler.solve_and_install_schedule(NaiveSolver)
    client_procnode.scheduler.solve_and_install_schedule(NoTimeSolver)

    server_procnode.start()
    client_procnode.start()
    ns.sim_run()

    client_results = client_procnode.scheduler.get_batch_results()
    server_results = server_procnode.scheduler.get_batch_results()

    return BqcResult(client_results, server_results)


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

    LogManager.set_log_level("DEBUG")
    LogManager.log_to_file("test_run.log")

    def check(alpha, beta, theta1, theta2, expected):
        ns.sim_reset()
        bqc_result = run_bqc(
            alpha=alpha, beta=beta, theta1=theta1, theta2=theta2, num_iterations=1
        )

        server_batch_results = bqc_result.server_results
        for batch_id, batch_results in server_batch_results.items():
            program_results = batch_results.results
            m2s = [result.values["m2"] for result in program_results]
            # assert all(m2 == expected for m2 in m2s)
            print(len([m2 for m2 in m2s if m2 == expected]))

    check(alpha=8, beta=8, theta1=0, theta2=0, expected=0)
    # check(alpha=8, beta=24, theta1=0, theta2=0, expected=1)
    # check(alpha=8, beta=8, theta1=13, theta2=27, expected=0)
    # check(alpha=8, beta=24, theta1=2, theta2=22, expected=1)


if __name__ == "__main__":
    # test_bqc_1()
    # test_bqc_2()
    test_bqc()
