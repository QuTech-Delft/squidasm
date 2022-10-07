from __future__ import annotations

from typing import Any, Dict, List, Optional

import netsquid as ns

from squidasm.qoala.runtime.config import ProcNodeNetworkConfig
from squidasm.qoala.runtime.context import SimulationContext
from squidasm.qoala.runtime.environment import GlobalEnvironment
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.schedule import Schedule
from squidasm.qoala.sim.build import build_network
from squidasm.qoala.sim.globals import GlobalSimData
from squidasm.qoala.sim.network import ProcNodeNetwork


def _run(network: ProcNodeNetwork) -> List[Dict[str, Any]]:
    """Run the protocols of a network and programs running in that network.

    :param network: `ProcNodeNetwork` representing the nodes and links
    :return: final results of the programs
    """

    # Start the link protocols.
    for link in network.links:
        link.start()

    # Start the node protocols.
    for _, node in network.nodes.items():
        node.start()

    # Start the NetSquid simulation.
    ns.sim_run()

    return [node.scheduler.get_results() for _, node in network.nodes.items()]


def run(
    config: ProcNodeNetworkConfig,
    programs: Dict[str, List[ProgramInstance]],
    schedules: Optional[Dict[str, Schedule]] = None,
    num_times: int = 1,
) -> List[Dict[str, Any]]:
    """Run programs on a network specified by a network configuration.

    :param config: configuration of the network
    :param programs: dictionary of node names to programs
    :param num_times: numbers of times to run the programs, defaults to 1
    :return: program results
    """
    # Create global runtime environment.
    rte = GlobalEnvironment()

    # Build the network. Info about created nodes will be added to the runtime environment.
    network = build_network(config, rte)

    ###########################################
    # TODO: pass context to simulation objects!
    ###########################################
    sim_data = GlobalSimData()
    sim_data.set_network(network)
    context = SimulationContext(global_env=rte, global_sim_data=sim_data)
    print(context)

    for name, program_list in programs.items():
        for program in program_list:
            network.nodes[name]._local_env.register_program(program)

    if schedules is not None:
        for name, schedule in schedules.items():
            network.nodes[name]._local_env.install_local_schedule(schedule)

    for name in programs.keys():
        network.nodes[name].install_environment()

    results = _run(network)
    return results
