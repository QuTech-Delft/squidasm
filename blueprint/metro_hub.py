from __future__ import annotations

from typing import Optional

from netsquid.nodes import Node


class MetroHubNode(Node):
    def __init__(
        self,
        name: str,
        node_id: Optional[int] = None,
    ) -> None:

        super().__init__(name, ID=node_id)

