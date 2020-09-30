_CURRENT_BACKEND = [None]


def get_running_backend(block=True):
    while True:
        backend = _CURRENT_BACKEND[0]
        if backend is not None:
            return backend
        if not block:
            return None


def get_current_nodes(block=True):
    backend = get_running_backend(block=block)
    return backend.nodes


def get_current_node_names(block=True):
    backend = get_running_backend(block=block)
    return backend.nodes.keys()


def get_current_node_ids(block=True):
    backend = get_running_backend(block=block)
    return {node_name: node.ID for node_name, node in backend.nodes.items()}


def get_current_app_node_mapping(block=True):
    backend = get_running_backend(block=block)
    return backend.app_node_map


def get_node_id_for_app(app_name):
    app_node_map = get_current_app_node_mapping()
    node = app_node_map.get(app_name)
    if node is None:
        raise ValueError(f"No app with name {app_name} mapped to a node")
    return node.ID


def get_node_name_for_app(app_name):
    app_node_map = get_current_app_node_mapping()
    node = app_node_map.get(app_name)
    if node is None:
        raise ValueError(f"No app with name {app_name} mapped to a node")
    return node.name


def get_node_id(name):
    current_node_ids = get_current_node_ids()
    node_id = current_node_ids.get(name)
    if node_id is None:
        raise ValueError(f"Unknown node with name {name}")
    return node_id


def get_node_name(node_id):
    current_node_ids = get_current_node_ids()
    for node_name, tmp_node_id in current_node_ids.items():
        if tmp_node_id == node_id:
            return node_name
    raise ValueError(f"Unknown node with id {node_id}")


def put_current_backend(backend):
    if _CURRENT_BACKEND[0] is not None:
        raise RuntimeError("Already a backend running")
    else:
        _CURRENT_BACKEND[0] = backend


def pop_current_backend():
    _CURRENT_BACKEND[0] = None
