from netsquid_netbuilder.modules.links.interface import ILinkConfig


def set_heralded_side_parameters(config: ILinkConfig, param_key: str, default_vals: dict):
    param_key_a = param_key + "_A"
    param_key_b = param_key + "_B"
    default = getattr(config, param_key)
    if default is None:
        if param_key in default_vals.keys():
            default = default_vals[param_key]
        else:
            raise NotImplementedError(f"No default specified for param: {param_key} of {config.__class__.__name__}")
    if getattr(config, param_key_a) is None:
        setattr(config, param_key_a, default)
    if getattr(config, param_key_b) is None:
        setattr(config, param_key_b, default)


def set_heralded_side_length(config: ILinkConfig):
    param_key_a = "length_A"
    param_key_b = "length_B"
    default = getattr(config, "length")

    if getattr(config, param_key_a) is None:
        setattr(config, param_key_a, default / 2)
    if getattr(config, param_key_b) is None:
        setattr(config, param_key_b, default / 2)
