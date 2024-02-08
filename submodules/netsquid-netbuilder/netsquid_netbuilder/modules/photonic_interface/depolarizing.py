from __future__ import annotations

import numpy as np
from netsquid.qubits import DenseDMRepr
from netsquid.qubits.qrepr import QRepr
from netsquid_magic.photonic_interface_interface import (
    IPhotonicInterface,
    IPhotonicInterfaceBuilder,
    IPhotonicInterfaceConfig,
)
from netsquid_netbuilder.util.fidelity import fidelity_to_prob_max_mixed


class DepolarizingPhotonicInterfaceConfig(IPhotonicInterfaceConfig):
    fidelity: float = 0
    """Probability of producing a maximally mixed state"""
    p_loss: float = 0
    """Probability of losing the photon in the conversion"""


class DepolarizingPhotonicInterface(IPhotonicInterface):
    def __init__(self, config: DepolarizingPhotonicInterfaceConfig):
        self.fidelity = config.fidelity
        self.p_loss = config.p_loss

    @property
    def probability_success(self) -> float:
        return 1 - self.p_loss

    def operate(self, state: QRepr) -> QRepr:
        if self.fidelity == 0:
            return state

        maximally_mixed = np.array(
            [[0.25, 0, 0, 0], [0, 0.25, 0, 0], [0, 0, 0.25, 0], [0, 0, 0, 0.25]],
            dtype=complex,
        )

        prob_max_mixed = fidelity_to_prob_max_mixed(self.fidelity)

        original_state = state.reduced_dm()
        return DenseDMRepr(
            num_qubits=state.num_qubits,
            dm=prob_max_mixed * maximally_mixed
               + (1 - prob_max_mixed) * original_state,
        )


class DepolarizingPhotonicInterfaceBuilder(IPhotonicInterfaceBuilder):
    @classmethod
    def build(
        cls, photonic_interface_cfg: IPhotonicInterfaceConfig
    ) -> IPhotonicInterface:
        if not isinstance(photonic_interface_cfg, DepolarizingPhotonicInterfaceConfig):
            raise TypeError(
                f"Expected type: {DepolarizingPhotonicInterfaceConfig}"
                f"got: {type(photonic_interface_cfg)}"
            )
        return DepolarizingPhotonicInterface(photonic_interface_cfg)
