from enum import Enum

from netsquid.components import Component


class NoiseType(Enum):
    NoNoise = "NoNoise"
    Depolarise = "Depolarise"
    Bitflip = "Bitflip"


class NodeLinkConfig(Component):
    """
    Describes a connection between two nodes that can generate entanglement
    with each other.

    `NodeLinkConfig`s are used to create a `MagicDistributor` from, in the
    context of a network that can map node names to actual Node objects.

    Parameters
    ----------
    `noise_type`: either a `NoiseType` variant, or a string. A string is
        automatically converted into the corresponding variant.
        The string representation is convenient for writing it in a
        `network.yaml` file.
    `fidelity`: float
        Fidelity of the link. What this means exactly depends on the noise type.

    """
    def __init__(self, name, node_name1: str, node_name2: str, noise_type=NoiseType.NoNoise, fidelity=1):
        super().__init__(name)
        self.node_name1: str = node_name1
        self.node_name2: str = node_name2
        self.noise_type = NoiseType(noise_type)
        self.fidelity = fidelity
