from __future__ import annotations

from typing import Optional

from netsquid.components import QuantumProcessor
from netsquid.nodes import Node

from netsquid_driver.driver import Driver


class NodeWithDriver(Node):
    def __init__(
        self,
        name: str,
        node_id: Optional[int] = None,
    ) -> None:
        super().__init__(name, ID=node_id)
        driver = Driver(f"Driver_{name}")
        self.add_subcomponent(driver, "driver")

    @property
    def driver(self) -> Driver:
        return self.subcomponents["driver"]


class QDeviceNode(NodeWithDriver):
    """A node that has a Quantum device."""

    def __init__(
        self,
        name: str,
        qdevice: QuantumProcessor,
        qdevice_type: str,
        node_id: Optional[int] = None,
    ) -> None:
        super().__init__(name, node_id=node_id)
        self.qmemory = qdevice
        self.qmemory_typ = qdevice_type

    @property
    def qdevice(self) -> QuantumProcessor:
        return self.qmemory


class ProcessingNode(QDeviceNode):
    pass


class RepeaterNode(QDeviceNode):
    pass


class MetroHubNode(NodeWithDriver):
    pass
