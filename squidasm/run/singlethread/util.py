import importlib
import re
import sys
from typing import Callable


def load_program(filename: str) -> Callable:
    spec = importlib.util.spec_from_file_location("module", filename)  # type: ignore
    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    func = getattr(module, "main")
    return func  # type: ignore


def modify_and_import(module_name, package):
    spec = importlib.util.find_spec(module_name, package)
    source = spec.loader.get_source(module_name)
    lines = source.splitlines()
    new_lines = []
    socket_name = None
    epr_socket_name = None
    for line in lines:
        new_lines.append(line)
        if re.search(r"\w+\.flush\(\)", line):
            new_line = re.sub(r"(\w+\.flush\(\))", r"(yield from \1)", line)
            new_lines[-1] = new_line
            continue
        sck_result = re.search(r" (\w+) = Socket\(", line)
        epr_result = re.search(r" (\w+) = EPRSocket\(", line)
        if sck_result is not None:
            socket_name = sck_result.group(1)
        if epr_result is not None:
            epr_socket_name = epr_result.group(1)
        if socket_name is None and epr_socket_name is None:
            continue
        if re.search(fr"{socket_name}\.recv\(\)", line) and not re.search(
            fr"{epr_socket_name}\.recv\(\)", line
        ):
            new_line = re.sub(
                fr"{socket_name}.recv\(\)", f"(yield from {socket_name}.recv())", line
            )
            new_lines[-1] = new_line

    new_source = "\n".join(new_lines)
    module = importlib.util.module_from_spec(spec)
    codeobj = compile(new_source, module.__spec__.origin, "exec")
    exec(codeobj, module.__dict__)
    sys.modules[module_name] = module
    return module
