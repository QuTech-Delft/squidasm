from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.models.delaymodels import FibreDelayModel
from netsquid.nodes.connections import DirectConnection
from netsquid.nodes.node import Node
from netsquid.components import QuantumMemory, QuantumProcessor
from netsquid.components.models.qerrormodels import QuantumErrorModel

import netsquid_netconf
from netsquid_netconf.builder import ComponentBuilder
from netsquid_netconf.netconf import netconf_generator, Loader, _nested_dict_set


class ClassicalFibreDirectConnection(DirectConnection):
    """A direct connection composed of symmetric classical fibres."""

    def __init__(self, name, **properties):
        # For testing purposes so it's visible if LIST and RANGE works
        print("Creating direct connection {} with properties {}".format(name, properties))

        super().__init__(
            name=name,
            channel_AtoB=ClassicalChannel(
                name="AtoB",
                models={"delay_model": FibreDelayModel()},
                **properties,
            ),
            channel_BtoA=ClassicalChannel(
                name="BtoA",
                models={"delay_model": FibreDelayModel()},
                **properties,
            ),
        )


def test_1():
    ComponentBuilder.add_type("classical_fibre_direct_connection", ClassicalFibreDirectConnection)
    ComponentBuilder.add_type("MyQMem", QuantumMemory)
    ComponentBuilder.add_type("quantum_processor", QuantumProcessor)
    ComponentBuilder.add_type("q_noise_model", QuantumErrorModel)

    generator = netconf_generator("./tests/test_network_config/config1.yaml")
    config = next(generator)
    print(config)
    print(f"NodeA.qmemory: {config['components']['NodeA'].qmemory}")
    print(f"NodeA.qmemory.num_positions: {config['components']['NodeA'].qmemory.num_positions}")
    print(f"NodeA.qmemory.phys_instructions: {config['components']['NodeA'].qmemory.get_physical_instructions()}")
    print(f"NodeB.qmemory: {config['components']['NodeB'].qmemory}")

if __name__ == '__main__':
    test_1()
