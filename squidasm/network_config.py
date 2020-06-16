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


class NodeLink(Component):
    def __init__(self, name, node_name1: str, node_name2: str, noise_type: str = "NoNoise", fidelity: float = 1):
        super().__init__(name)
        self.node_name1: str = node_name1
        self.node_name2: str = node_name2
        self.noise_type = NoiseType.from_str(noise_type)
        self.fidelity = fidelity


class DepolariseStateSamplerFactory(HeraldedStateDeliverySamplerFactory):
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
    def __init__(self, nodes, noise, **kwargs):
        self.noise = noise
        super().__init__(delivery_sampler_factory=DepolariseStateSamplerFactory(), nodes=nodes, **kwargs)

    def add_delivery(self, memory_positions, **kwargs):
        return super().add_delivery(memory_positions=memory_positions, noise=self.noise, **kwargs)


class BitflipStateSamplerFactory(HeraldedStateDeliverySamplerFactory):
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
    def __init__(self, nodes, flip_prob, **kwargs):
        self.flip_prob = flip_prob
        super().__init__(delivery_sampler_factory=BitflipStateSamplerFactory(), nodes=nodes, **kwargs)

    def add_delivery(self, memory_positions, **kwargs):
        return super().add_delivery(memory_positions=memory_positions, flip_prob=self.flip_prob, **kwargs)
