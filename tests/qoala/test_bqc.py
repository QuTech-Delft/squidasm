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
from squidasm.qoala.runtime.program import ProgramInput, ProgramInstance, ProgramResult
from squidasm.qoala.runtime.schedule import ProgramTaskList
from squidasm.qoala.sim.build import build_generic_qprocessor
from squidasm.qoala.sim.csocket import ClassicalSocket
from squidasm.qoala.sim.egp import EgpProtocol
from squidasm.qoala.sim.hostinterface import HostInterface
from squidasm.qoala.sim.memory import ProgramMemory, SharedMemory, Topology, UnitModule
from squidasm.qoala.sim.process import IqoalaProcess
from squidasm.qoala.sim.procnode import ProcNode
from squidasm.util.tests import has_multi_state, has_state, netsquid_run, yield_from


def create_process(
    pid: int,
    program: IqoalaProgram,
    unit_module: UnitModule,
    host_interface: HostInterface,
    inputs: Optional[Dict[str, Any]] = None,
) -> IqoalaProcess:
    if inputs is None:
        inputs = {}
    prog_input = ProgramInput(values=inputs)
    instance = ProgramInstance(
        pid=pid,
        program=program,
        inputs=prog_input,
        tasks=ProgramTaskList.empty(program),
    )
    mem = ProgramMemory(pid=0, unit_module=unit_module)

    process = IqoalaProcess(
        prog_instance=instance,
        prog_memory=mem,
        csockets={
            id: ClassicalSocket(host_interface, name)
            for (id, name) in program.meta.csockets.items()
        },
        epr_sockets=program.meta.epr_sockets,
        subroutines=program.subroutines,
        requests=program.requests,
        result=ProgramResult(values={}),
    )
    return process


def create_qprocessor(name: str, num_qubits: int) -> QuantumProcessor:
    cfg = GenericQDeviceConfig.perfect_config(num_qubits=num_qubits)
    return build_generic_qprocessor(name=f"{name}_processor", cfg=cfg)


def create_global_env(
    num_qubits: int, names: List[str] = ["alice", "bob", "charlie"]
) -> GlobalEnvironment:

    env = GlobalEnvironment()
    for i, name in enumerate(names):
        env.add_node(i, GlobalNodeInfo.default_nv(name, i, num_qubits))
    return env


def create_procnode(
    name: str,
    env: GlobalEnvironment,
    num_qubits: int,
    procnode_cls: Type[ProcNode] = ProcNode,
    asynchronous: bool = False,
) -> ProcNode:
    alice_qprocessor = create_qprocessor(name, num_qubits)

    node_id = env.get_node_id(name)
    procnode = procnode_cls(
        name=name,
        global_env=env,
        qprocessor=alice_qprocessor,
        node_id=node_id,
        asynchronous=asynchronous,
    )

    return procnode


def create_egp_protocols(node1: Node, node2: Node) -> Tuple[EgpProtocol, EgpProtocol]:
    link_dist = PerfectStateMagicDistributor(nodes=[node1, node2], state_delay=1000.0)
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[node1, node2],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    return EgpProtocol(node1, link_prot), EgpProtocol(node2, link_prot)


class BqcProcNode(ProcNode):
    def run_epr_subroutine(
        self, process: IqoalaProcess, subrt_name: str
    ) -> Generator[EventExpression, None, None]:
        subrt = process.subroutines[subrt_name]
        epr_instr_idx = None
        for i, instr in enumerate(subrt.subroutine.instructions):
            if isinstance(instr, CreateEPRInstruction) or isinstance(
                instr, RecvEPRInstruction
            ):
                epr_instr_idx = i
                break

        # Set up arrays
        for i in range(epr_instr_idx):
            yield from self.qnos.processor.assign(process, subrt_name, i)

        request_name = subrt.request_name
        assert request_name is not None
        request = process.requests[request_name].request

        # Handle request
        yield from self.netstack.processor.assign(process, request)

        # Execute wait instruction
        yield from self.qnos.processor.assign(process, subrt_name, epr_instr_idx + 1)

        # Return subroutine results
        self.host.processor.copy_subroutine_results(process, subrt_name)

    def run_subroutine(
        self, process: IqoalaProcess, subrt_name: str
    ) -> Generator[EventExpression, None, None]:
        subrt = process.subroutines[subrt_name]
        num_instrs = len(subrt.subroutine.instructions)

        for i in range(num_instrs):
            yield from self.qnos.processor.assign(process, subrt_name, i)

        # Return subroutine results
        self.host.processor.copy_subroutine_results(process, subrt_name)


class ServerProcNode(BqcProcNode):
    def run(self) -> Generator[EventExpression, None, None]:
        self.finished = False

        process = self.memmgr.get_process(0)
        self.scheduler.initialize(process)

        # csocket = assign_cval() : 0
        yield from self.host.processor.assign(process, 0)

        # run_subroutine(vec<client_id>) : create_epr_0
        yield from self.host.processor.assign(process, 1)
        yield from self.run_epr_subroutine(process, "create_epr_0")

        # run_subroutine(vec<client_id>) : create_epr_1
        yield from self.host.processor.assign(process, 2)
        yield from self.run_epr_subroutine(process, "create_epr_1")

        # run_subroutine(vec<client_id>) : local_cphase
        yield from self.host.processor.assign(process, 3)
        yield from self.run_subroutine(process, "local_cphase")

        # delta1 = recv_cmsg(client_id)
        yield from self.host.processor.assign(process, 4)

        # vec<m1> = run_subroutine(vec<delta1>) : meas_qubit_1
        yield from self.host.processor.assign(process, 5)
        yield from self.run_subroutine(process, "meas_qubit_1")

        # send_cmsg(csocket, m1)
        yield from self.host.processor.assign(process, 6)
        # delta2 = recv_cmsg(csocket)
        yield from self.host.processor.assign(process, 7)

        # vec<m2> = run_subroutine(vec<delta2>) : meas_qubit_0
        yield from self.host.processor.assign(process, 8)
        yield from self.run_subroutine(process, "meas_qubit_0")

        # return_result(m1)
        yield from self.host.processor.assign(process, 9)
        # return_result(m2)
        yield from self.host.processor.assign(process, 10)

        self.finished = True


class ClientProcNode(BqcProcNode):
    def run(self) -> Generator[EventExpression, None, None]:
        self.finished = False

        process = self.memmgr.get_process(0)
        self.scheduler.initialize(process)

        # csocket = assign_cval() : 0
        yield from self.host.processor.assign(process, 0)

        # run_subroutine(vec<>) : create_epr_0
        yield from self.host.processor.assign(process, 1)
        yield from self.run_epr_subroutine(process, "create_epr_0")

        # run_subroutine(vec<theta2>) : post_epr_0
        yield from self.host.processor.assign(process, 2)
        yield from self.run_subroutine(process, "post_epr_0")

        # run_subroutine(vec<>) : create_epr_1
        yield from self.host.processor.assign(process, 3)
        yield from self.run_epr_subroutine(process, "create_epr_1")

        # run_subroutine(vec<theta1>) : post_epr_1
        yield from self.host.processor.assign(process, 4)
        yield from self.run_subroutine(process, "post_epr_1")

        # x = mult_const(p1) : 16
        # minus_theta1 = mult_const(theta1) : -1
        # delta1 = add_cval_c(minus_theta1, x)
        # delta1 = add_cval_c(delta1, alpha)
        # send_cmsg(server_id, delta1)
        for i in range(5, 10):
            yield from self.host.processor.assign(process, i)

        # m1 = recv_cmsg(csocket)
        yield from self.host.processor.assign(process, 10)

        # y = mult_const(p2) : 16
        # minus_theta2 = mult_const(theta2) : -1
        # beta = bcond_mult_const(beta, m1) : -1
        # delta2 = add_cval_c(beta, minus_theta2)
        # delta2 = add_cval_c(delta2, y)
        # send_cmsg(csocket, delta2)
        for i in range(11, 17):
            yield from self.host.processor.assign(process, i)

        # return_result(p1)
        yield from self.host.processor.assign(process, 17)
        # return_result(p2)
        yield from self.host.processor.assign(process, 18)

        self.finished = True


@dataclass
class BqcResult:
    client_process: IqoalaProcess
    server_process: IqoalaProcess
    client_procnode: BqcProcNode
    server_procnode: BqcProcNode


def run_bqc(
    server_prot: Type[BqcProcNode],
    client_prot: Type[BqcProcNode],
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

    server_procnode = create_procnode(
        "server", global_env, num_qubits, procnode_cls=server_prot
    )
    server_process = create_process(
        pid=0,
        program=server_program,
        unit_module=unit_module,
        host_interface=server_procnode.host._interface,
        inputs={"client_id": client_id},
    )
    server_procnode.add_process(server_process)

    path = os.path.join(os.path.dirname(__file__), "bqc_client.iqoala")
    with open(path) as file:
        client_text = file.read()
    client_program = IqoalaParser(client_text).parse()

    client_procnode = create_procnode(
        "client", global_env, num_qubits, procnode_cls=client_prot
    )
    client_process = create_process(
        pid=0,
        program=client_program,
        unit_module=unit_module,
        host_interface=client_procnode.host._interface,
        inputs={
            "server_id": server_id,
            "alpha": alpha,
            "beta": beta,
            "theta1": theta1,
            "theta2": theta2,
        },
    )
    client_procnode.add_process(client_process)

    client_egp, server_egp = create_egp_protocols(
        client_procnode.node, server_procnode.node
    )
    client_procnode.egpmgr.add_egp(server_id, client_egp)
    server_procnode.egpmgr.add_egp(client_id, server_egp)

    client_procnode.connect_to(server_procnode)

    # client_egp._ll_prot.start()
    server_procnode.start()
    client_procnode.start()
    ns.sim_run()

    assert client_procnode.finished
    assert server_procnode.finished

    return BqcResult(
        client_process=client_process,
        server_process=server_process,
        client_procnode=client_procnode,
        server_procnode=server_procnode,
    )


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


def test_bqc_1():
    class ServerProcNode(BqcProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            self.finished = False

            process = self.memmgr.get_process(0)
            self.scheduler.initialize(process)

            # csocket = assign_cval() : 0
            yield from self.host.processor.assign(process, 0)

            # run_subroutine(vec<client_id>) : create_epr_0
            yield from self.host.processor.assign(process, 1)
            yield from self.run_epr_subroutine(process, "create_epr_0")

            # run_subroutine(vec<client_id>) : create_epr_1
            yield from self.host.processor.assign(process, 2)
            yield from self.run_epr_subroutine(process, "create_epr_1")

            self.finished = True

    class ClientProcNode(BqcProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            self.finished = False

            process = self.memmgr.get_process(0)
            self.scheduler.initialize(process)

            # csocket = assign_cval() : 0
            yield from self.host.processor.assign(process, 0)

            # run_subroutine(vec<>) : create_epr_0
            yield from self.host.processor.assign(process, 1)
            yield from self.run_epr_subroutine(process, "create_epr_0")

            # run_subroutine(vec<theta2>) : post_epr_0
            yield from self.host.processor.assign(process, 2)
            yield from self.run_subroutine(process, "post_epr_0")

            # run_subroutine(vec<>) : create_epr_1
            yield from self.host.processor.assign(process, 3)
            yield from self.run_epr_subroutine(process, "create_epr_1")

            # run_subroutine(vec<theta1>) : post_epr_1
            yield from self.host.processor.assign(process, 4)
            yield from self.run_subroutine(process, "post_epr_1")

            # x = mult_const(p1) : 16
            # minus_theta1 = mult_const(theta1) : -1
            # delta1 = add_cval_c(minus_theta1, x)
            # delta1 = add_cval_c(delta1, alpha)
            # send_cmsg(server_id, delta1)
            for i in range(5, 10):
                yield from self.host.processor.assign(process, i)

            self.finished = True

    alpha_beta_theta1_theta2 = [
        (0, 0, 0, 0),
        (0, 8, 0, 0),
        (8, 0, 0, 0),
        (8, 8, 0, 0),
    ]

    for (alpha, beta, theta1, theta2) in alpha_beta_theta1_theta2:
        for _ in range(10):
            result = run_bqc(
                ServerProcNode, ClientProcNode, alpha, beta, theta1, theta2
            )

            p1 = result.client_process.host_mem.read("p1")
            p2 = result.client_process.host_mem.read("p2")
            delta1 = result.client_process.host_mem.read("delta1")
            q0 = result.server_procnode.qdevice.get_local_qubit(0)
            q1 = result.server_procnode.qdevice.get_local_qubit(1)

            assert delta1 == alpha - theta1 + p1 * 16

            # p2 and theta2 control state of q0
            expected_q0 = expected_rsp_state(theta2, p2, dummy=False)
            assert has_state(q0, expected_q0)

            # p1 and theta1 control state of q1
            expected_q1 = expected_rsp_state(theta1, p1, dummy=False)
            assert has_state(q1, expected_q1)


def test_bqc_2():
    class ServerProcNode(BqcProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            self.finished = False

            process = self.memmgr.get_process(0)
            self.scheduler.initialize(process)

            # csocket = assign_cval() : 0
            yield from self.host.processor.assign(process, 0)

            # run_subroutine(vec<client_id>) : create_epr_0
            yield from self.host.processor.assign(process, 1)
            yield from self.run_epr_subroutine(process, "create_epr_0")

            # run_subroutine(vec<client_id>) : create_epr_1
            yield from self.host.processor.assign(process, 2)
            yield from self.run_epr_subroutine(process, "create_epr_1")

            # run_subroutine(vec<client_id>) : local_cphase
            yield from self.host.processor.assign(process, 3)
            yield from self.run_subroutine(process, "local_cphase")

            # delta1 = recv_cmsg(client_id)
            yield from self.host.processor.assign(process, 4)

            # vec<m1> = run_subroutine(vec<delta1>) : meas_qubit_1
            yield from self.host.processor.assign(process, 5)
            yield from self.run_subroutine(process, "meas_qubit_1")

            # send_cmsg(csocket, m1)
            yield from self.host.processor.assign(process, 6)
            # delta2 = recv_cmsg(csocket)
            yield from self.host.processor.assign(process, 7)

            self.finished = True

    class ClientProcNode(BqcProcNode):
        def run(self) -> Generator[EventExpression, None, None]:
            self.finished = False

            process = self.memmgr.get_process(0)
            self.scheduler.initialize(process)

            # csocket = assign_cval() : 0
            yield from self.host.processor.assign(process, 0)

            # run_subroutine(vec<>) : create_epr_0
            yield from self.host.processor.assign(process, 1)
            yield from self.run_epr_subroutine(process, "create_epr_0")

            # run_subroutine(vec<theta2>) : post_epr_0
            yield from self.host.processor.assign(process, 2)
            yield from self.run_subroutine(process, "post_epr_0")

            # run_subroutine(vec<>) : create_epr_1
            yield from self.host.processor.assign(process, 3)
            yield from self.run_epr_subroutine(process, "create_epr_1")

            # run_subroutine(vec<theta1>) : post_epr_1
            yield from self.host.processor.assign(process, 4)
            yield from self.run_subroutine(process, "post_epr_1")

            # x = mult_const(p1) : 16
            # minus_theta1 = mult_const(theta1) : -1
            # delta1 = add_cval_c(minus_theta1, x)
            # delta1 = add_cval_c(delta1, alpha)
            # send_cmsg(server_id, delta1)
            for i in range(5, 10):
                yield from self.host.processor.assign(process, i)

            # m1 = recv_cmsg(csocket)
            yield from self.host.processor.assign(process, 10)

            # y = mult_const(p2) : 16
            # minus_theta2 = mult_const(theta2) : -1
            # beta = bcond_mult_const(beta, m1) : -1
            # delta2 = add_cval_c(beta, minus_theta2)
            # delta2 = add_cval_c(delta2, y)
            # send_cmsg(csocket, delta2)
            for i in range(11, 17):
                yield from self.host.processor.assign(process, i)

            self.finished = True

    alpha_beta_theta1_theta2 = [
        (0, 0, 0, 0),
        (0, 8, 0, 0),
        (8, 0, 0, 0),
        (8, 8, 0, 0),
    ]

    for (alpha, beta, theta1, theta2) in alpha_beta_theta1_theta2:
        for _ in range(10):
            result = run_bqc(
                ServerProcNode, ClientProcNode, alpha, beta, theta1, theta2
            )

            p1 = result.client_process.host_mem.read("p1")
            p2 = result.client_process.host_mem.read("p2")
            delta1 = result.client_process.host_mem.read("delta1")
            m1 = result.client_process.host_mem.read("m1")
            delta2 = result.client_process.host_mem.read("delta2")

            q0 = result.server_procnode.qdevice.get_local_qubit(0)
            print(q0.qstate)

            assert delta1 == alpha - theta1 + p1 * 16
            assert delta2 == math.pow(-1, m1) * beta - theta2 + p2 * 16


def test_bqc():

    # Effective computation: measure in Z the following state:
    # H Rz(beta) H Rz(alpha) |+>
    # m2 should be this outcome

    # angles are in multiples of pi/16

    def check(alpha, beta, theta1, theta2, expected):
        results = [
            run_bqc(
                server_prot=ServerProcNode,
                client_prot=ClientProcNode,
                alpha=alpha,
                beta=beta,
                theta1=theta1,
                theta2=theta2,
            )
            for _ in range(10)
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
