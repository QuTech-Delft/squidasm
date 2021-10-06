from __future__ import annotations

from typing import Any, List

import yaml
from pydantic import BaseModel


def _from_file(path: str, typ: Any) -> Any:
    with open(path, "r") as f:
        raw_config = yaml.load(f, Loader=yaml.Loader)
        return typ(**raw_config)


class GenericQDeviceConfig(BaseModel):
    # total number of qubits
    num_qubits: int = 2
    # number of communication qubits
    num_comm_qubits: int = 2

    # coherence times (same for each qubit)
    T1: int = 10_000_000_000
    T2: int = 1_000_000_000

    # gate execution times
    init_time: int = 10_000
    single_qubit_gate_time: int = 1_000
    two_qubit_gate_time: int = 100_000
    measure_time: int = 10_000

    # noise model
    single_qubit_gate_depolar_prob: float = 0.0
    two_qubit_gate_depolar_prob: float = 0.01

    @classmethod
    def from_file(cls, path: str) -> GenericQDeviceConfig:
        return _from_file(path, GenericQDeviceConfig)

    @classmethod
    def perfect_config(cls) -> GenericQDeviceConfig:
        cfg = GenericQDeviceConfig()
        cfg.single_qubit_gate_depolar_prob = 0.0
        cfg.two_qubit_gate_depolar_prob = 0.0
        return cfg


class NVQDeviceConfig(BaseModel):
    # number of qubits per NV
    num_qubits: int = 2

    # initialization error of the electron spin
    electron_init_depolar_prob: float = 0.05

    # error of the single-qubit gate
    electron_single_qubit_depolar_prob: float = 0.0

    # measurement errors (prob_error_X is the probability that outcome X is flipped to 1 - X)
    prob_error_0: float = 0.05
    prob_error_1: float = 0.005

    # initialization error of the carbon nuclear spin
    carbon_init_depolar_prob: float = 0.05

    # error of the Z-rotation gate on the carbon nuclear spin
    carbon_z_rot_depolar_prob: float = 0.001

    # error of the native NV two-qubit gate
    ec_gate_depolar_prob: float = 0.008

    # coherence times
    electron_T1: int = 1_000_000_000
    electron_T2: int = 300_000_000
    carbon_T1: int = 150_000_000_000
    carbon_T2: int = 1_500_000_000

    # gate execution times
    carbon_init: int = 310_000
    carbon_rot_x: int = 500_000
    carbon_rot_y: int = 500_000
    carbon_rot_z: int = 500_000
    electron_init: int = 2_000
    electron_rot_x: int = 5
    electron_rot_y: int = 5
    electron_rot_z: int = 5
    ec_controlled_dir_x: int = 500_000
    ec_controlled_dir_y: int = 500_000
    measure: int = 3_700

    @classmethod
    def from_file(cls, path: str) -> NVQDeviceConfig:
        return _from_file(path, NVQDeviceConfig)

    @classmethod
    def perfect_config(cls) -> NVQDeviceConfig:
        # get default config
        cfg = NVQDeviceConfig()

        # set all error params to 0
        cfg.electron_init_depolar_prob = 0
        cfg.electron_single_qubit_depolar_prob = 0
        cfg.prob_error_0 = 0
        cfg.prob_error_1 = 0
        cfg.carbon_init_depolar_prob = 0
        cfg.carbon_z_rot_depolar_prob = 0
        cfg.ec_gate_depolar_prob = 0
        return cfg


class StackConfig(BaseModel):
    name: str
    qdevice_typ: str
    qdevice_cfg: Any

    @classmethod
    def from_file(cls, path: str) -> StackConfig:
        return _from_file(path, StackConfig)

    @classmethod
    def perfect_generic_config(cls, name: str) -> StackConfig:
        return StackConfig(
            name=name,
            qdevice_typ="generic",
            qdevice_cfg=GenericQDeviceConfig.perfect_config(),
        )


class DepolariseLinkConfig(BaseModel):
    fidelity: float
    prob_success: float
    t_cycle: float

    @classmethod
    def from_file(cls, path: str) -> DepolariseLinkConfig:
        return _from_file(path, DepolariseLinkConfig)


class NVLinkConfig(BaseModel):
    length_A: float
    length_B: float
    full_cycle: float
    cycle_time: float
    alpha: float

    @classmethod
    def from_file(cls, path: str) -> NVLinkConfig:
        return _from_file(path, NVLinkConfig)


class HeraldedLinkConfig(BaseModel):
    length: float
    p_loss_init: float = 0
    p_loss_length: float = 0.25
    speed_of_light: float = 200_000
    dark_count_probability: float = 0
    detector_efficiency: float = 1.0
    visibility: float = 1.0
    num_resolving: bool = False

    @classmethod
    def from_file(cls, path: str) -> HeraldedLinkConfig:
        return _from_file(path, HeraldedLinkConfig)


class LinkConfig(BaseModel):
    stack1: str
    stack2: str
    typ: str
    cfg: Any

    @classmethod
    def from_file(cls, path: str) -> LinkConfig:
        return _from_file(path, LinkConfig)

    @classmethod
    def perfect_config(cls, stack1: str, stack2: str) -> LinkConfig:
        return LinkConfig(stack1=stack1, stack2=stack2, typ="perfect", cfg=None)


class StackNetworkConfig(BaseModel):
    stacks: List[StackConfig]
    links: List[LinkConfig]

    @classmethod
    def from_file(cls, path: str) -> StackNetworkConfig:
        return _from_file(path, StackNetworkConfig)
