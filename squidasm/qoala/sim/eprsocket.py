from dataclasses import dataclass


@dataclass
class EprSocket:
    """EPR Socket. Allows for EPR pair generation with a single remote node.

    Multiple EPR Sockets may be created for a single pair of nodes. These
    sockets have a different ID, and may e.g be used for EPR generation requests
    with different parameters."""

    socket_id: int
    remote_id: int
    fidelity: float
