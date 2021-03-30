import ast
import inspect
import logging
import math
import re
import time
from collections import defaultdict
from typing import Callable, Dict, Generator, List, Tuple

from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.epr_socket import EPRSocket

# from squidasm.run.singlethread import NetQASMConnection, NetSquidContext, Socket, util


class _AddYieldFrom(ast.NodeTransformer):
    def visit_Call(self, node):
        if hasattr(node.func, "attr"):
            if (
                node.func.attr in ["recv", "flush"]
                and node.func.value.id != "epr_socket"
            ):
                func_call = f"{node.func.value.id}.{node.func.attr}()"
                print(f"NOTE: rewriting '{func_call}' to 'yield from {func_call}'")
                new_node = ast.YieldFrom(node)
                ast.copy_location(new_node, node)
                ast.fix_missing_locations(new_node)
                self.generic_visit(node)
                return new_node
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        new_node = node
        new_node.name = "_compiled_as_generator"
        new_node.decorator_list = []

        ast.copy_location(new_node, node)
        ast.fix_missing_locations(new_node)
        self.generic_visit(node)
        return new_node


def make_generator(func: Callable) -> Generator:
    f = inspect.getsource(func)
    tree = ast.parse(f)
    tree = _AddYieldFrom().visit(tree)
    recompiled = compile(tree, "<ast>", "exec")

    exec(recompiled, globals(), locals())

    gen = locals()["_compiled_as_generator"]
    return gen
