"""Utility functions for examples"""
from typing import List

import netsquid.qubits
import numpy as np
from deprecated import deprecated
from netqasm.sdk.qubit import Qubit
from netsquid.qubits import operators
from netsquid.qubits import qubitapi as qapi
from netsquid_netbuilder.modules.links.depolarise import DepolariseLinkConfig
from netsquid_netbuilder.base_configs import (
    CLinkConfig,
    LinkConfig,
    ProcessingNodeConfig,
    NetworkConfig,
)
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig

import squidasm.sim.stack.globals


def get_qubit_state(q: Qubit, node_name, full_state=False) -> np.ndarray:
    """
    Retrieves the underlying quantum state from a qubit in density matrix formalism.
     This is only possible in simulation.

    .. note:: The function gets the *current* qubit. So make sure the subroutine is flushed
              before calling the method.

    :param q: The qubit to get the state of or list of qubits.
    :param node_name:  Node name of current node.
    Requirement for this parameter is due to software limitation,
     can be made unnecessary in future version of SquidASM.
    :param full_state: Flag to retrieve the full underlying entangled state and not only this qubit subspace.
    :return: An array that is the density matrix description of the quantum state
    """
    # Get the executor and qmemory from the backend
    network = squidasm.sim.stack.globals.GlobalSimData.get_network()
    app_id = q._conn.app_id

    executor = network.stacks[node_name].qnos.app_memories[app_id]
    qmemory = network.stacks[node_name].qdevice

    # Get the physical position of the qubit
    virtual_address = q.qubit_id
    phys_pos = executor.phys_id_for(virt_id=virtual_address)

    # Get the netsquid qubit
    ns_qubit = qmemory.mem_positions[phys_pos].get_qubit()

    if full_state:
        ns_qubit = ns_qubit.qstate.qubits

    dm = qapi.reduced_dm(ns_qubit)

    return dm


def get_reference_state(phi: float, theta: float) -> np.ndarray:
    """
    Gives the reference quantum state for a qubit in density matrix formalism,
     that is in a pure state matching a state on the Bloch sphere described by the angles phi and theta.

    :param phi: Angle on Bloch sphere between state and x-axis
    :param theta: Angle on Bloch sphere between state and z-axis
    :return: An array that is the density matrix description of the quantum state
    """
    q = netsquid.qubits.create_qubits(1)[0]
    rot_y = operators.create_rotation_op(theta, (0, 1, 0))
    rot_z = operators.create_rotation_op(phi, (0, 0, 1))
    netsquid.qubits.operate(q, rot_y)
    netsquid.qubits.operate(q, rot_z)
    return qapi.reduced_dm(q)


@deprecated(
    reason="Same and more functionality achieved by "
    "`netsquid_netbuilder.util.network_generation.create_simple_network`",
    version="0.12.1",
)
def create_two_node_network(
    node_names: List[str] = None,
    link_noise: float = 0,
    qdevice_noise: float = 0,
    clink_delay: float = 0.0,
    link_delay: float = 0.0,
) -> NetworkConfig:
    """
    Create a network configuration with two nodes, with simple noise models.
    :param node_names: List of str with the names of the two nodes
    :param link_noise: A number between 0 and 1 that indicates how noisy the generated EPR pairs are.
    :param qdevice_noise: A number between 0 and 1 that indicates how noisy the qubit operations on the nodes are.
    :param clink_delay: The time, in nanoseconds, it takes for the classical message to arrive.
    :param link_delay: The time, in nanoseconds, it takes for an EPR pair to be generated.
    :return: StackNetworkConfig object with a two node network
    """
    node_names = ["Alice", "Bob"] if node_names is None else node_names
    assert len(node_names) == 2

    qdevice_cfg = GenericQDeviceConfig.perfect_config()
    qdevice_cfg.two_qubit_gate_depolar_prob = qdevice_noise
    qdevice_cfg.single_qubit_gate_depolar_prob = qdevice_noise
    processing_nodes = [
        ProcessingNodeConfig(name=name, qdevice_typ="generic", qdevice_cfg=qdevice_cfg)
        for name in node_names
    ]

    link_cfg = DepolariseLinkConfig(
        fidelity=1 - link_noise * 3 / 4, t_cycle=link_delay, prob_success=1
    )
    link = LinkConfig(
        stack1=node_names[0], stack2=node_names[1], typ="depolarise", cfg=link_cfg
    )
    clink = CLinkConfig(
        stack1=node_names[0],
        stack2=node_names[1],
        typ="default",
        cfg=DefaultCLinkConfig(delay=clink_delay),
    )
    return NetworkConfig(processing_nodes=processing_nodes, links=[link], clinks=[clink])
