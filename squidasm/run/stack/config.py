from __future__ import annotations

from typing import Any, List

import yaml
from pydantic import BaseModel


def _from_file(path: str, typ: Any) -> Any:
    with open(path, "r") as f:
        raw_config = yaml.load(f, Loader=yaml.Loader)
        return typ(**raw_config)


class GenericQDeviceConfig(BaseModel):
    """
    The configuration for a generic quantum device.
    """

    num_qubits: int = 2
    """Number of qubits in the quantum device."""
    num_comm_qubits: int = 2
    """Number of communication qubits. Not used."""

    # coherence times (same for each qubit)
    T1: float = 10_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds."""
    T2: float = 1_000_000_000
    """Dephasing or transverse relaxation time in nanoseconds."""

    # gate execution times
    init_time: float = 10_000
    """Qubit initialization time in nanoseconds."""
    single_qubit_gate_time: float = 1_000
    """Single qubit gate execution time in nanoseconds."""
    two_qubit_gate_time: float = 100_000
    """Two qubit gate execution time in nanoseconds."""
    measure_time: float = 10_000
    """Qubit measurement time in nanoseconds."""

    # noise model
    single_qubit_gate_depolar_prob: float = 0.0
    """Probability of error in each single qubit gate operation. """
    two_qubit_gate_depolar_prob: float = 0.01
    """Probability of error in each two qubit gate operation."""

    @classmethod
    def from_file(cls, path: str) -> GenericQDeviceConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, GenericQDeviceConfig)  # type: ignore

    @classmethod
    def perfect_config(cls) -> GenericQDeviceConfig:
        """Create a configuration for a device without any noise or errors."""
        cfg = GenericQDeviceConfig()
        cfg.init_time = 0
        cfg.single_qubit_gate_depolar_prob = 0
        cfg.two_qubit_gate_depolar_prob = 0
        cfg.measure_time = 0
        cfg.single_qubit_gate_depolar_prob = 0.0
        cfg.two_qubit_gate_depolar_prob = 0.0
        return cfg


class NVQDeviceConfig(BaseModel):
    """
    The configuration for a NV quantum device.
    """

    # number of qubits per NV
    num_qubits: int = 2
    """Number of qubits in the quantum device."""

    # single electron noise
    electron_init_depolar_prob: float = 0.05
    """Probability of error during electron initialization."""
    electron_single_qubit_depolar_prob: float = 0.0
    """Probability of error during electron single gate operation."""

    # measurement errors electron
    prob_error_0: float = 0.05
    """Probability of measuring a 1 instead of 0 in an electron measurement."""
    prob_error_1: float = 0.005
    """Probability of measuring a 0 instead of 1 in an electron measurement."""

    # single carbon noise
    carbon_init_depolar_prob: float = 0.05
    """Probability of error during carbon initialization."""
    carbon_z_rot_depolar_prob: float = 0.001
    """Probability of error during carbon single gate operation."""

    ec_gate_depolar_prob: float = 0.008
    """Probability of error during native NV two qubit operation between electron and carbon."""

    # coherence times
    electron_T1: float = 1_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds for the electron."""
    electron_T2: float = 300_000_000
    """Dephasing or transverse relaxation time in nanoseconds for the electron."""
    carbon_T1: float = 150_000_000_000
    """Energy or longitudinal relaxation time in nanoseconds for carbon qubits."""
    carbon_T2: float = 1_500_000_000
    """Dephasing or transverse relaxation time in nanoseconds for carbon qubits.."""

    # gate execution times
    carbon_init: float = 310_000
    """Carbon qubit initialization time in nanoseconds."""
    carbon_rot_x: float = 500_000
    """Carbon x rotation gate time in nanoseconds."""
    carbon_rot_y: float = 500_000
    """Carbon y rotation gate time in nanoseconds."""
    carbon_rot_z: float = 500_000
    """Carbon z rotation gate time in nanoseconds."""
    electron_init: float = 2_000
    """Electron qubit initialization time in nanoseconds."""
    electron_rot_x: float = 5
    """Electron x rotation gate time in nanoseconds."""
    electron_rot_y: float = 5
    """Electron y rotation gate time in nanoseconds."""
    electron_rot_z: float = 5
    """Electron z rotation gate time in nanoseconds."""
    ec_controlled_dir_x: float = 500_000
    """Two qubit controlled x rotation gate time in nanoseconds."""
    ec_controlled_dir_y: float = 500_000
    """Two qubit controlled y rotation gate time in nanoseconds."""
    measure: float = 3_700
    """Electron measurement time in nanoseconds."""

    @classmethod
    def from_file(cls, path: str) -> NVQDeviceConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, NVQDeviceConfig)  # type: ignore

    @classmethod
    def perfect_config(cls) -> NVQDeviceConfig:
        """Create a configuration for a device without any noise or errors."""
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
    """Configuration for a single stack (i.e. end node)."""

    name: str
    """Name of the stack."""
    qdevice_typ: str
    """Type of the quantum device."""
    qdevice_cfg: Any
    """Configuration of the quantum device, allowed configuration depends on type."""

    @classmethod
    def from_file(cls, path: str) -> StackConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, StackConfig)  # type: ignore

    @classmethod
    def perfect_generic_config(cls, name: str) -> StackConfig:
        """Create a configuration for a stack with a generic quantum device without any noise or errors."""
        return StackConfig(
            name=name,
            qdevice_typ="generic",
            qdevice_cfg=GenericQDeviceConfig.perfect_config(),
        )


class DepolariseLinkConfig(BaseModel):
    """Simple model for a link to generate EPR pairs."""

    fidelity: float
    """Fidelity of successfully generated EPR pairs."""
    prob_success: float
    """Probability of successfully generating an EPR per cycle."""
    t_cycle: float
    """Duration of a cycle in nano seconds."""

    @classmethod
    def from_file(cls, path: str) -> DepolariseLinkConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, DepolariseLinkConfig)  # type: ignore


class NVLinkConfig(BaseModel):
    length_A: float
    length_B: float
    full_cycle: float
    cycle_time: float
    alpha: float

    @classmethod
    def from_file(cls, path: str) -> NVLinkConfig:
        return _from_file(path, NVLinkConfig)  # type: ignore


class HeraldedLinkConfig(BaseModel):
    """The heralded link uses a model with both nodes connected by fiber to a midpoint station with a
    Bell-state measurement detector.
    The nodes repeatedly send out entangled photons and, on a successful measurement at the midpoint,
    the midpoint station will send out a signal to both nodes, heralding successful entanglement.
    The heralded link uses the double click model as developed and described by:
    https://arxiv.org/abs/2207.10579"""

    length: float
    """Total length of the heralded connection in km. (i.e. sum of fibers on both sides on midpoint station)"""
    p_loss_init: float = 0
    """Probability that photons are lost when entering connection the connection on either side."""
    p_loss_length: float = 0.25
    """Attenuation coefficient [dB/km] of fiber on either side."""
    speed_of_light: float = 200_000
    """Speed of light [km/s] in fiber on either side."""
    dark_count_probability: float = 0
    """dark-count probability per detection."""
    detector_efficiency: float = 1.0
    """Probability that the presence of a photon leads to a detection event."""
    visibility: float = 1.0
    """Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)"""
    num_resolving: bool = False
    """Determines whether photon-number-resolving detectors are used for the Bell-state measurement."""

    @classmethod
    def from_file(cls, path: str) -> HeraldedLinkConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, HeraldedLinkConfig)  # type: ignore


class LinkConfig(BaseModel):
    """Configuration for a single link."""

    stack1: str
    """Name of the first stack being connected via link."""
    stack2: str
    """Name of the second stack being connected via link."""
    typ: str
    """Type of the link."""
    cfg: Any
    """Configuration of the link, allowed configuration depends on type."""

    @classmethod
    def from_file(cls, path: str) -> LinkConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, LinkConfig)  # type: ignore

    @classmethod
    def perfect_config(cls, stack1: str, stack2: str) -> LinkConfig:
        """Create a configuration for a link without any noise or errors."""
        return LinkConfig(stack1=stack1, stack2=stack2, typ="perfect", cfg=None)


class StackNetworkConfig(BaseModel):
    """Full network configuration."""

    stacks: List[StackConfig]
    """List of all the stacks in the network."""
    links: List[LinkConfig]
    """List of all the links connecting the stacks in the network."""

    @classmethod
    def from_file(cls, path: str) -> StackNetworkConfig:
        """Load the configuration from a YAML file."""
        return _from_file(path, StackNetworkConfig)  # type: ignore
