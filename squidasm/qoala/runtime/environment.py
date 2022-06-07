from typing import Dict, Tuple


class GlobalNodeInfo:
    pass


class GlobalLinkInfo:
    pass


class GlobalEnvironment:
    # node ID -> node info
    _nodes: Dict[int, GlobalNodeInfo] = {}

    # (node A ID, node B ID) -> link info
    # for a pair (a, b) there exists no separate (b, a) info (it is the same)
    _links: Dict[Tuple[int, int], GlobalLinkInfo] = {}


class LocalNodeInfo:
    pass


class LocalLinkInfo:
    pass


class LocalEnvironment:
    _global_env: GlobalEnvironment

    # node ID of self
    _node_id: int


class ProgramEnvironment:
    pass
