from __future__ import annotations

from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.sdk.qubit import Qubit
from netsquid_magic.link_layer import (
    MagicLinkLayerProtocolWithSignaling,
    SingleClickTranslationUnit,
)
from netsquid_magic.magic_distributor import PerfectStateMagicDistributor

from pydynaa import EventExpression
from squidasm.sim.stack.config import NVQDeviceConfig, build_nv_qdevice
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.sim.stack.stack import NodeStack


class ClientProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={},
            csockets=["bob"],
            epr_sockets=["bob"],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets["bob"]

        csocket = context.csockets["bob"]
        msg = yield from csocket.recv()
        print(f"got message from bob: {msg}")

        q = Qubit(conn)
        q.X()
        m = q.measure()
        yield from conn.flush()

        print(f"m = {m}")

        q = epr_socket.create()[0]
        epr_outcome = q.measure()
        yield from conn.flush()
        print(f"epr_outcome = {epr_outcome}")


class ServerProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={},
            csockets=["alice"],
            epr_sockets=["alice"],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets["alice"]
        csocket = context.csockets["alice"]

        csocket.send("hello")

        q = Qubit(conn)
        q.X()
        m = q.measure()
        print(f"time before measuring: {ns.sim_time()}")
        yield from conn.flush()
        print(f"time after measuring: {ns.sim_time()}")

        print(f"m = {m}")

        q = epr_socket.recv()[0]
        epr_outcome = q.measure()
        yield from conn.flush()
        print(f"epr_outcome = {epr_outcome}")


if __name__ == "__main__":
    alice_qdevice = build_nv_qdevice("nv_qdevice_alice", cfg=NVQDeviceConfig())
    alice = NodeStack("alice", qdevice=alice_qdevice)
    bob_qdevice = build_nv_qdevice("nv_qdevice_bob", cfg=NVQDeviceConfig())
    bob = NodeStack("bob", qdevice=bob_qdevice)

    # link_dist = NVSingleClickMagicDistributor(
    #     nodes=[alice.node, bob.node],
    #     length_A=10,
    #     length_B=10,
    #     full_cycle=10,
    #     t_cycle=10,
    # )
    link_dist = PerfectStateMagicDistributor(nodes=[alice.node, bob.node])
    link_prot = MagicLinkLayerProtocolWithSignaling(
        nodes=[alice.node, bob.node],
        magic_distributor=link_dist,
        translation_unit=SingleClickTranslationUnit(),
    )
    alice.assign_ll_protocol(link_prot)
    bob.assign_ll_protocol(link_prot)

    alice.connect_to(bob)

    alice.host.add_program(ClientProgram())
    bob.host.add_program(ServerProgram())

    NetSquidContext.set_nodes({0: "alice", 1: "bob"})

    link_prot.start()
    alice.start()
    bob.start()

    ns.sim_run()
