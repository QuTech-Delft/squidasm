from enum import Enum, auto

import numpy as np
import netsquid as ns
from netsquid_magic.magic_distributor import MagicDistributor
from netsquid_magic.state_delivery_sampler import HeraldedStateDeliverySamplerFactory
from netsquid.components import Component


class NoiseType(Enum):
    NoNoise = auto()
    Depolarise = auto()
    BitFlip = auto()

    @staticmethod
    def from_str(name: str):
        if name == "NoNoise":
            return NoiseType.NoNoise
        elif name == "Depolarise":
            return NoiseType.Depolarise
        elif name == "BitFlip":
            return NoiseType.BitFlip
        else:
            raise TypeError(f"Noise type {name} not valid")


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

        if isinstance(noise_type, str):
            self.noise_type = NoiseType.from_str(noise_type)
        else:
            self.noise_type = noise_type
        self.fidelity = fidelity


class DepolariseStateSamplerFactory(HeraldedStateDeliverySamplerFactory):
    """
    A factory for samplers that produce either an EPR pair, or the maximally
    mixed state over the two 2 nodes (I/4). The latter is samples with
    probablity `noise`.
    """
    def __init__(self):
        super().__init__(func_delivery=self._delivery_func,
                         func_success_probability=self._get_success_probability)

    @staticmethod
    def _delivery_func(noise, **kwargs):
        epr_state = np.array(
            [[0.5, 0, 0, 0.5],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0.5, 0, 0, 0.5]],
            dtype=np.complex)
        maximally_mixed = np.array(
            [[0.25, 0, 0, 0],
             [0, 0.25, 0, 0],
             [0, 0, 0.25, 0],
             [0, 0, 0, 0.25]],
            dtype=np.complex)
        return [epr_state, maximally_mixed], [1 - noise, noise]

    @staticmethod
    def _get_success_probability(**kwargs):
        return 1


class DepolariseMagicDistributor(MagicDistributor):
    """
    Distributes (noisy) EPR pairs to 2 connected nodes, using samplers created
    by a `DepolariseStateSamplerFactory`.
    """
    def __init__(self, nodes, noise, **kwargs):
        self.noise = noise
        super().__init__(delivery_sampler_factory=DepolariseStateSamplerFactory(), nodes=nodes, **kwargs)

    def add_delivery(self, memory_positions, **kwargs):
        return super().add_delivery(memory_positions=memory_positions, noise=self.noise, **kwargs)


class BitflipStateSamplerFactory(HeraldedStateDeliverySamplerFactory):
    """
    A factory for samplers that produce either a perfect EPR pair,
    or an EPR pair where an X gate is applied to one of the qubits ("bit flip").
    The bit flip happens with probability `flip_prob`.
    """
    def __init__(self):
        super().__init__(func_delivery=self._delivery_bit_flip,
                         func_success_probability=self._get_success_probability)

    @staticmethod
    def _delivery_bit_flip(flip_prob, **kwargs):
        return [ns.b00, ns.b01], [1 - flip_prob, flip_prob]

    @staticmethod
    def _get_success_probability(**kwargs):
        return 1


class BitflipMagicDistributor(MagicDistributor):
    """
    Distributes (noisy) EPR pairs to 2 connected nodes, using samplers created
    by a `BitflipSamplerFactory`.
    """
    def __init__(self, nodes, flip_prob, **kwargs):
        self.flip_prob = flip_prob
        super().__init__(delivery_sampler_factory=BitflipStateSamplerFactory(), nodes=nodes, **kwargs)

    def add_delivery(self, memory_positions, **kwargs):
        return super().add_delivery(memory_positions=memory_positions, flip_prob=self.flip_prob, **kwargs)
